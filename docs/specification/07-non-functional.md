# 07 Non-functional requirements

## Secrets and logging (mandatory, see ADR-0011)
- No secret in the repository; secrets come from environment variables or GitHub Secrets and have no default values.
- The application refuses to start without required secrets, and in `demo`/`prod` rejects short or well-known weak ones.
- Secrets, password hashes, tokens and full database URLs are never logged. Secret settings use `SecretStr`; SQL parameters are hidden; all log output passes through a redacting formatter.
- `ci-secrets` (repository rules and Gitleaks, redacted output) is a required check before merge; `make install-hooks` runs the same rules before each commit.
- A secret that reaches git history is treated as leaked and rotated.

## Security
- Passwords: argon2id, minimum 10 characters. Never logged or returned.
- Reset and refresh tokens stored only as hashes; reset tokens single use, 1 hour expiry.
- All traffic over HTTPS in production. Secure headers. Strict CORS.
- Input validation on every endpoint (Pydantic). Parameterised queries only (SQLAlchemy).
- Rate limiting and login throttling. Generic error messages on login and forgot-password (no user enumeration).
- Secrets only in environment variables; `.env` never committed.
- Personal data (email, mobile) limited to roles that need it. Provide a way to delete an account.
- Dependency scanning in CI.

## Performance
- Search p95 under 500 ms with 100,000 freelancers on a single small PostgreSQL instance.
- Indexes per the data model; verify slow queries with `EXPLAIN`.
- List endpoints always paginated.

## Reliability and operations
- Docker Compose for local development: `db`, `api`, `worker`, `web`. Demo hosting, CI/CD and backups: see [09-infrastructure.md](09-infrastructure.md).
- Config through environment variables; health endpoint `/health`.
- Structured JSON logs with request ids.
- Database backups documented; migrations run automatically in deploy and are reversible.

## Testing
- Backend: pytest with a real PostgreSQL (Docker locally, service container in CI); unit tests for services, API tests for every endpoint, migration up/down test.
- Frontend: Vitest and React Testing Library for components and key flows.
- CI on every pull request: lint, type check, tests, migration check, OpenAPI schema diff.

## Compatibility
- API usable from browsers and native mobile clients without change (bearer tokens, JSON, no cookies).

## Documentation
- OpenAPI always current. README per top-level folder. Specification and ADRs updated with behaviour or architecture changes.
