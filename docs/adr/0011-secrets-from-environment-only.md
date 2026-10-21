# ADR-0011: Secrets come from the environment only, and are checked before merge

- **Status:** Accepted
- **Date:** 2026-10-22
- **Deciders:** Project owner

## Context

Passwords, tokens and keys in source code, configuration examples, workflow files or logs are the most common way a project leaks access. Several people will contribute, so rules must be automatic, not a matter of memory.

## Decision

1. **No secret in the repository.** Not in code, tests, Docker or compose files, workflows, Terraform, docs or examples. Committed examples (`.env.example`) contain empty values or placeholders.
2. **Secrets come from environment variables** (locally from a git-ignored `.env`, in CI from GitHub Secrets, on servers from the deploy pipeline). The application has no default value for any secret and refuses to start without them.
3. **No built-in defaults for settings.** Default values live only in `.env.example` (committed, no secrets); `make env` copies them to `.env` and adds a random database password. The application and docker compose require every setting as an environment variable and stop with a clear error naming the missing variable. `ENVIRONMENT` must be one of `local`, `ci`, `demo`, `prod`, so a typo cannot skip the strict checks.
4. **Strong secrets in `demo` and `prod`.** At startup the application rejects a missing, short (under 16 characters) or well-known weak database password when `ENVIRONMENT` is `demo` or `prod`. Error messages never contain the secret.
5. **Secrets never appear in logs.** Secrets are `SecretStr` (they print as masked), SQL parameters are hidden, and every log line passes through a redacting formatter that masks URL credentials, `password=`/`token=`/`secret=` style pairs, bearer tokens and the exact secret values the application knows.
6. **Automated check before merge.** The `ci-secrets` workflow runs `scripts/check-secrets.sh` (file and line only, never the matching text) and Gitleaks with `--redact` over every commit of a pull request. It is a required status check on `main`. `make install-hooks` runs the same script before each local commit.
7. **Exceptions are explicit.** A line that looks like a secret but is not may carry the marker `secret-scan:allow`. Reviewers look at every use of the marker.

## Alternatives considered

- Relying on review only: misses things and does not scale with contributors.
- A secrets manager (AWS Secrets Manager, SSM) for the demo: better for production; planned with the production architecture ADR. Environment variables stay the interface to the application either way.

## Consequences

- Local setup needs one extra step (`make env`) that generates a random database password.
- CI needs the repository secret `CI_DB_PASSWORD` (any random string).
- A leaked secret must be rotated, not just deleted: git history keeps it. Report it to the maintainers immediately.
- The checks can produce false positives; use `secret-scan:allow` sparingly or adjust the rules in a pull request.
