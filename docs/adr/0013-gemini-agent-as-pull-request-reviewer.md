# ADR-0013: Gemini agent as an advisory pull request reviewer

- Status: Proposed
- Date: 2026-10-25
- Deciders: Project owner

## Context

Pull requests are currently reviewed by the project owner alone (see [CODEOWNERS](../../.github/CODEOWNERS)
and [CONTRIBUTING](../../CONTRIBUTING.md)). A second, tireless reader that checks every diff against the
project's own rules would catch mistakes early. The repository already contains a placeholder:
`.github/workflows/gemini-pr-review.yml` (manual `workflow_dispatch`), an empty
`.github/scripts/review_agent.py` and an empty `.github/review_context.md`.

Problems with the placeholder as written:

- `gh pr diff` does not accept git pathspecs (`-- ':!package-lock.json'`), so the filter step would fail. Filtering
  must be done on the downloaded diff or using standard Unix stream tools.
- The lockfile names are for other stacks (`go.sum`, `yarn.lock`); this repo uses `package-lock.json`, Alembic
  migrations, Terraform and Markdown.
- Arbitrary truncation (`head -c 40000`) cuts the diff in the middle of a file or line without notifying the model.
- It runs on a self-hosted runner. A runner executing workflows touching a public repository must never
  receive untrusted fork code together with secrets.
- Actions are tagged (`@v4`), not pinned to an immutable commit SHA.
- The review script and context are empty.

This ADR decides how the reviewer is integrated and provides the **review brief**: the repository
and application context the reviewer is given, written as a principal engineer briefing a colleague.

## Decision

### 1. Integration

1. A custom GitHub Actions workflow calls the Gemini API with a key stored as the repository secret
   `GEMINI_API_KEY` (environment variable only, per [ADR-0011](0011-secrets-from-environment-only.md)).
2. The reviewer is **advisory**. It posts one summary comment (updated in place on each run) and never approves,
   requests changes, or becomes a required status check. The human reviewer decides.
3. Trigger: `pull_request` (`opened`, `synchronize`, `ready_for_review`) for branches in this repository only
   (`head.repo.full_name == github.repository`), plus the existing manual `workflow_dispatch` for re-runs.
   Forks, Draft PRs (`if: github.event.pull_request.draft == false`), and Dependabot PRs are skipped.
   `pull_request_target` is **not** used.
4. Permissions: `contents: read`, `pull-requests: write`, nothing else. Third-party actions pinned to full commit
   SHAs. Runs on `ubuntu-latest` (GitHub-hosted, ephemeral) rather than the self-hosted runner.
5. Input to the model:
   - PR metadata (title, description, changed-file list);
   - The diff with generated/bulky assets removed (`package-lock.json`, `*.svg`, `*.png`, `*.min.js`);
   - `.github/review_context.md` embedding the review brief in Part B;
   - A hard character threshold (~40,000 characters). Diffs exceeding the limit are truncated **at file or hunk boundaries**, with omitted files explicitly listed so the reviewer notes them as unreviewed rather than hallucinating.
6. Prompt-injection hardening: PR diff, title, and description are isolated as `UNTRUSTED_DATA`. The model has no system tools, cannot run code, and its output is length-capped plain text with `@mentions` neutralized before posting.
7. Data and secret handling:
   - Secret scanning runs on the complete untruncated diff prior to model submission. If matched, execution aborts with a security notice comment.
   - API keys and raw payload dumps are masked (`::add-mask::`).
   - Google AI Studio Paid Tier / Vertex billing is enforced so input code is not retained or used for Google model training.
8. Cost and abuse control: A `concurrency` group cancels obsolete runs on new pushes; token usage is capped per request alongside Google Cloud budget alerts.
9. Output format: Findings grouped as **Blocker / Should fix / Consider**, citing file and line, evidence, and suggestions. "No findings" is valid when code meets all criteria.