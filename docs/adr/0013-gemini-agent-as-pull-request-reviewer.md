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
   SHAs. Runs on `ubuntu-latest` (GitHub-hosted, ephemeral) rather than the self-hosted runner. The workflow checks out the **base** commit, never the PR branch, so a PR cannot change the script, or the brief, that runs with the API key; changes to the reviewer take effect after merge.
5. Input to the model:
   - PR metadata (title, description, changed-file list);
   - The diff with generated/bulky assets removed (`package-lock.json`, `*.svg`, `*.png`, `*.min.js`);
   - `.github/review_context.md`, the review brief (folder structure, application idea, security, performance, structural flaws, process-flow invariants), kept in step with the code and specification and limited to 6000 characters;
   - A hard character threshold (~40,000 characters). Diffs exceeding the limit are truncated **at file or hunk boundaries**, with omitted files explicitly listed so the reviewer notes them as unreviewed rather than hallucinating.
6. Prompt-injection hardening: PR diff, title, and description are sent inside one block with a random per-run delimiter and treated as untrusted data. The model has no system tools, cannot run code, and its output is length-capped plain text with `@mentions` neutralized before posting.
7. Data and secret handling:
   - Secret scanning runs on the complete untruncated diff prior to model submission. If matched, execution aborts with a security notice comment.
   - The API key, the request and the diff are never printed to logs. Only added lines outside test files are scanned (`ci-secrets` covers test files).
   - Google AI Studio Paid Tier / Vertex billing is enforced so input code is not retained or used for Google model training.
8. Cost and abuse control: A `concurrency` group cancels obsolete runs on new pushes; token usage is capped per request alongside Google Cloud budget alerts.
9. Output format: Findings grouped as **Blocker / Should fix / Consider**, citing file and line, evidence, and suggestions. "No findings" is valid when code meets all criteria.

### 2. Second reviewer on demand

A separate manual-only workflow (`claude-pr-review.yml`) runs the same script with `REVIEW_PROVIDER=claude` and the secret `ANTHROPIC_API_KEY`. It never runs automatically, posts a separate comment, and follows the same rules as above (base-branch script, no PR code, advisory, no secrets in logs).

### 3. Output shape: summary plus review threads

The model returns structured output (overview, risk, summary, findings with file and line). The script posts one summary comment, updated in place and starting with a short "What this PR does" overview, and posts each finding that points at a changed line as an inline review comment, so people can reply and resolve it. Earlier findings and their replies are given back to the model on later runs and are not raised twice. Line numbers come from an annotated diff and are checked against it before posting; anything that cannot be placed goes into the summary.

### 4. Failure behaviour

- A failed or empty model answer posts nothing and fails the job; because the check is not required, merging is not blocked.
- A cut-off answer (output limit) is posted with a note saying later findings may be missing.
- The script lists every file it did not send under "Not reviewed".

### 5. Component-aware review (added 2026-10)

The repository has several components (backend, web, mobile, infrastructure, CI, documentation). The decision is to keep **one workflow per reviewer and one script**, and make the script component-aware, instead of one workflow per component:

- Pull requests often span components, and the most valuable check is between them (API versus web and mobile clients). Separate workflows would split the review into several comments and none would see both sides.
- A component map (`.github/review/components.json`) selects short per-component briefs, so the reviewer gets the right rules without one ever-growing brief.
- Files are packed by priority (source, configuration, tests, documentation) within a size budget; when a change is too large, each component gets its own model request and the answers are merged. One extra request checks the API contract when the backend and a client change together.
- Generated files are excluded, key stores and similar files stop the review by name, and the first lines of changed source files are given to the model to avoid "undefined name" mistakes.
- Costs: up to four component requests plus one contract request on large mixed pull requests; most pull requests remain one request.

## Alternatives considered

- **Gemini Code Assist GitHub app.** No code to maintain, but less control over context, output format, data sent and cost. A valid fallback if the script becomes a burden.
- **Agentic reviewer with repository access or tools.** More capable, but untrusted PR text plus tools is a much larger attack surface. Rejected for an advisory reviewer.
- **Required check that blocks merge.** Rejected: model output is non-deterministic. Deterministic checks (lint, types, tests, secrets, audit) remain the required gates.
- **No automated reviewer.** Cheapest, but leaves one human as the only reader of every diff.

## Consequences

- Every pull request gets a consistent second opinion against the project's own rules at low cost.
- False positives and misses are possible; the severity format and "no findings" answer limit noise.
- Code leaves GitHub for Google's API, so the paid-tier requirement must be confirmed before enabling.
- `review_context.md` becomes a maintained document: update it in the same pull request when architecture, process rules or the specification change. A stale brief produces wrong findings.
- A new secret, vendor and recurring cost are owned by the project owner.
