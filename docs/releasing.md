# Versions and releases

Every build has a version, and every release has a Git tag, a GitHub Release with a changelog, and container images with the same version. Nobody edits version numbers by hand.

## How a version is decided

The project uses [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`) driven by [Conventional Commits](https://www.conventionalcommits.org/). Pull requests are squash-merged, so **the pull request title becomes the commit message on `main`** and decides the next version. The `pr-title` check enforces the format.

| PR title starts with | Example | Effect on the version |
|---|---|---|
| `fix:` | `fix(api): reject empty labels` | patch (0.1.0 → 0.1.1) |
| `feat:` | `feat: add rating comments` | minor (0.1.1 → 0.2.0) |
| `feat!:` or a `BREAKING CHANGE:` footer | `feat!: rename the vouch status` | major (below 1.0 it bumps the minor instead) |
| `perf:` | `perf: index freelancer search` | patch |
| `docs:`, `chore:`, `ci:`, `test:`, `refactor:`, `style:`, `build:` | `chore(deps): bump vite` | none by themselves; they are included in the next release PR when a `feat` or `fix` also exists |

The subject starts with a lowercase letter. A scope in brackets is optional.

## What happens automatically

1. You merge changes to `main`. Each push builds both images (`build-images`) and deploys the demo (`deploy-demo`). These builds are versioned `X.Y.Z-dev.<short sha>`, where `X.Y.Z` is the last release, for example `0.1.0-dev.57def12`.
2. The `release` workflow keeps **one open pull request** titled `chore(main): release X.Y.Z`. It contains the new version in `backend/pyproject.toml` and `frontend/package.json`, `.release-please-manifest.json`, and the changelog entry in `CHANGELOG.md`.
3. **When you merge that release PR** (you decide when), the workflow creates the tag `vX.Y.Z` and a GitHub Release with the changelog, and `build-images` builds that commit as the release: images tagged `:vX.Y.Z`, `:X.Y.Z`, the commit SHA and `:demo`. `deploy-demo` then deploys it.

## Where to see the version

| Where | How |
|---|---|
| Running API | `curl https://skills-demo.privatedir.in/health` → `{"status":"ok","version":"0.1.0-dev.57def12"}`; also in the API docs (`/docs`) |
| Web build | `https://skills-demo.privatedir.in/version.txt` |
| Image | label `org.opencontainers.image.version`, plus `.revision` (commit) and `.source` |
| Deploy log | the smoke test step prints `Running version: …` |
| Releases | the repository's Releases page and `CHANGELOG.md` |

## Deploying or rolling back to a release

Actions → `deploy-demo` → Run workflow → image tag `v0.2.0` (or a 40-character commit SHA). A release tag also uses the deploy files (compose, scripts) from that tag.

## One-time repository setup

1. **Settings → Actions → General → Workflow permissions:** tick **Allow GitHub Actions to create and approve pull requests**. Without it the `release` workflow cannot open the release PR.
2. **Optional, but recommended:** create a fine-grained personal access token (Repository access: only this repository; permissions: Contents and Pull requests, both read and write) and store it as the repository secret `RELEASE_PLEASE_TOKEN`. A pull request opened with the default token does not start other workflows, so the release PR would show no checks and could not meet the required status checks. If you skip the token, close and reopen the release PR once to start the checks.
3. Add `pr-title` to the required status checks of the `main` ruleset (see the rulesets in the operations notes).

The first release PR counts only commits after `57def12`. Its version comes from the Conventional Commit types since then. Commits before that were not conventional enough to count.

## If something looks wrong

| Symptom | Cause and fix |
|---|---|
| No release PR appears | No `feat:` or `fix:` commit since the last release (docs and chore changes do not release), or setting 1 above is missing. Open Actions → `release` for the message. |
| PR title check fails | Change the title to `type: lowercase subject` and it re-runs. |
| Release PR shows no checks | Add the `RELEASE_PLEASE_TOKEN` secret, or close and reopen the PR. |
| The version in `/health` is `dev` | The image was built without the build argument (a local build). Release images and `build-images` set it. |
| Want a specific version | Put `Release-As: 1.0.0` as a footer line in a commit message on `main`; the next release PR uses it. |
