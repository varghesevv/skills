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
- Personal data (email, mobile) limited to the people who need it (see Privacy below). Provide a way to close an account that clears the personal details and keeps the trust record (FR-X-03).
- Authorisation reads the person's status from the database on every request; the token carries none (ADR-0017).
- Dependency scanning in CI.

## Privacy of verifier views

Decision D-07; this section settles the detail the functional requirements point to (FR-V-05).

- **Who sees a mobile number.** A searcher or above sees a provider's number only through the reveal endpoint. A verifier sees the numbers of people in their own scope on the verifier screens only. The scope of a person is the group they belong to (for an applicant: the group they chose at sign-up; for a revoked person: the group they were removed from), so a VERIFIER's scope is their group, an ADMIN's their church, the OWNER's everyone. **Purpose:** a leader is expected to know the people in their group and must be able to contact applicants and members to do so; the number is not offered for any other use, and applicants who have not chosen a group do not exist (sign-up needs one).
- **Where.** Only in the response of `GET /verifier/people/{id}`, one person at a time. Lists (`applicants`, `members`, `revoked`, `flagged`) never contain numbers. Search results and provider pages never do.
- **Logging.** Each call writes one `contact_views` row (who, whom, when, which screen), without the number. The log is readable by the OWNER only. Retention: open detail O-03.
- **Client handling.** The number is held only in memory while the screen is open, never written to disk, cache, logs, crash reports or analytics; the same rule as for reveal.
- **Closed accounts.** The personal details are cleared on closing, so nothing remains to view.

## Abuse limits for links and open endpoints

- Vouch links, group invitation links and admin invitations use at least 128 bits of randomness, are stored hashed, expire (vouch and invitation links 30 days by default, admin invitations 14 days; changeable by environment) and can be revoked. Answers for a wrong, expired or revoked link are identical (`404`), so nothing shows whether a link exists.
- Rate limits per IP and per person: link lookups 30 per hour, vouching 20 per day per person, sign-up 10 per hour per IP, the public church and group lists 60 per minute per IP. Beyond a limit: `429` with `Retry-After`. All limits are environment settings with these defaults.
- A person cannot vouch for themselves and cannot vouch twice for the same applicant.

## Notification delivery

- Notifications are written to the `notifications` table in the same transaction as the event that causes them, so none is lost or sent for a change that rolled back. Clients poll `GET /me/notifications` (every 60 seconds while the app is open, and on open). Email and push are later additions (decision D-09) and read from the same table.
- A notification names no person and carries no number; it holds the kind and the subject id, and clients load details through the normal endpoints.

## Performance
- Expected scale: about 10 000 people, at least 4 000 of them providers. Search p95 under 500 ms at that size, and still under 500 ms with ten times as many providers, on a single small PostgreSQL instance (measured in S5.2).
- The verifier lists (applicants, members) answer p95 under 300 ms for a church of 2 000 people.
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
