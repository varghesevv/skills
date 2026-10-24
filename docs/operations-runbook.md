# Operations runbook (demo environment)

For the person running the demo at `https://skills-demo.privatedir.in`. The environment is one AWS Lightsail instance with Docker Compose. Setup history and design are in [09-infrastructure.md](specification/09-infrastructure.md); the file layout is in [infra/README.md](../infra/README.md). Production will differ ([ADR-0012](adr/0012-production-on-ecs-fargate-and-rds.md)).

Rules that always apply:

- Secrets live only in the GitHub Environment `demo` and in `/opt/skills/.env` on the server (mode 600). Never paste them into chat, issues, pull requests or logs.
- Change the server only through the pipelines or Terraform, not by editing files by hand. A hand edit is overwritten by the next deploy.

## 1. Quick reference

| Thing | Where |
|---|---|
| Site | `https://skills-demo.privatedir.in` |
| Server | `13.127.253.202` (Lightsail instance `skills`, `ap-south-1`) |
| App folder on the server | `/opt/skills` |
| Deploy | GitHub → Actions → `deploy-demo` |
| Infrastructure changes | `make tf-plan` / `make tf-apply`, or Actions → `terraform-apply` |
| Backups | `s3://skills-demo-backups-<account>/postgres/`, kept 30 days |
| Logs | `docker compose --env-file .env -f compose.demo.yml logs -f api` (on the server) |

On the server, this shorthand saves typing (put it in your shell for the session):

```bash
cd /opt/skills
dc() { docker compose --env-file .env -f compose.demo.yml "$@"; }
dc ps
```

## 2. Log in to the server

SSH is allowed only from your addresses (`TF_SSH_ALLOWED_CIDRS`) and from the Lightsail browser console.

```bash
ssh -i ~/.ssh/skills-deploy deploy@13.127.253.202
```

- **"Operation timed out"**: your public address changed. Find it with `curl -s https://checkip.amazonaws.com`, update `ssh_allowed_cidrs` in `infra/terraform/envs/demo/terraform.tfvars` and the repository variable `TF_SSH_ALLOWED_CIDRS` (a JSON list such as `["203.0.113.10/32"]`), then `make tf-apply`. Meanwhile use the browser SSH: Lightsail console → instance `skills` → Connect.
- The deploy workflow opens port 22 for its own runner and restores your rule when it finishes.

## 3. Deploy

**Normal:** merge to `main` (versions and releases: [releasing.md](releasing.md)). If backend or frontend files changed, `build-images` builds and scans the images, then `deploy-demo` deploys that commit. Approve the `demo` Environment prompt if it appears.

**Infrastructure-only changes** (anything under `infra/`) do not build images. Deploy them by hand: Actions → `deploy-demo` → Run workflow (leave the tag empty to use the latest main commit; if the tag is empty and no image exists for that commit, give the tag of an existing image).

What the deploy does: assumes the `skills-deploy` role, opens SSH for the runner, writes `.env`, copies compose, Caddyfile and scripts, then `deploy.sh` pulls images, checks disk space, backs up the database, runs migrations, starts the stack, reloads Caddy, and the workflow smoke-tests the public URL.

If it fails, the log of the failing step says why. The stack keeps running the previous version when the failure happens before `up -d`.

## 4. Roll back

1. Find the previous good tag: Actions → earlier successful `deploy-demo` run → "Deploying image tag …", or on the server `cat /opt/skills/.deployed_tag` after the failed deploy (it shows the last *successful* tag).
2. Actions → `deploy-demo` → Run workflow → enter that tag: a 40-character commit SHA, or a release such as `v0.2.0`.
3. Migrations are meant to stay backward compatible for one release, so the old code works with the new schema. If a migration was destructive, restore the pre-deploy backup instead (section 6).

## 5. Secrets

Rotate by changing the secret in GitHub (Settings → Environments → `demo`), then running `deploy-demo`, which rewrites `.env`.

| Secret | Notes |
|---|---|
| `POSTGRES_PASSWORD` | Changing it breaks the running database login: the existing database keeps the old password. Change it inside PostgreSQL first (`dc exec db psql -U skills -c "ALTER USER skills PASSWORD '...'"` typed interactively, never with the value in the command history), then update the secret and deploy. |
| `JWT_SECRET` | At least 32 characters. Changing it signs everyone out. |
| `DEMO_USER_PASSWORD` | At least 16 characters. Only used when generating demo accounts; existing accounts keep the password they were created with. |
| `DEPLOY_SSH_PRIVATE_KEY` | Create a new key pair, append the new public key to `/home/deploy/.ssh/authorized_keys`, update the secret, deploy, then remove the old public key. |
| `BACKUP_AWS_ACCESS_KEY_ID` / `BACKUP_AWS_SECRET_ACCESS_KEY` | In the AWS console create a second access key for IAM user `skills-demo-backup`, update both secrets, deploy, then delete the old key. |

To check a value is present without showing it: `awk -F= '/^NAME=/{print length($2)}' /opt/skills/.env` prints its length.

## 6. Backups and restore drill

Backups run every night at 02:30 UTC and before every deploy. Do the drill after the first deploy and then every few months; a backup you have not restored is not a backup.

```bash
cd /opt/skills
./list-backups.sh                                    # pick the newest key, e.g. skills-20261022T023001Z.dump
./restore.sh postgres/skills-20261022T023001Z.dump   # restores into a NEW database "skills_restore"
```

It prints how long the restore took and the row counts. Compare with the live database:

```bash
dc exec -T db psql -U skills -d skills -c "SELECT count(*) FROM freelancers"
dc exec -T db psql -U skills -d skills_restore -c "SELECT count(*) FROM freelancers"
```

The numbers match if no one registered since that backup. Clean up afterwards:

```bash
dc exec -T db psql -U skills -d postgres -c 'DROP DATABASE skills_restore'
```

Write the date and the restore time in the project notes. **Disaster recovery** (replace the live database): `CONFIRM_REPLACE=yes ./restore.sh <key> skills`, then `dc up -d`. The instance itself can also be restored from a Lightsail snapshot (daily at 22:00 UTC) in the Lightsail console.

## 7. Monitoring and alarms

Three layers:

1. **Uptime check** (`uptime` workflow): every 15 minutes it calls `/health`, checks the API answers 401 without a login, the web page loads, and the certificate has more than 14 days left. A failed run emails the people who watch the repository's Actions (GitHub → Watch → Custom → Actions, and check Settings → Notifications). Set the repository variable `DEMO_URL` only if the address changes.
2. **Lightsail alarms** for CPU, status checks, burst capacity and outbound traffic. Create them once from your computer with an AWS profile that may use Lightsail:

   ```bash
   ALARM_EMAIL=you@example.com ./infra/scripts/setup-alarms.sh
   ```

   Click the confirmation link in the email Lightsail sends. Re-running the script updates the alarms.
3. **Disk space**: Lightsail has no disk metric, so `deploy.sh` refuses to deploy when the disk is 90% full and prints the usage on every deploy. Check by hand with `df -h /opt/skills`. To free space: `docker image prune -af`.

Test the alarms once: the quickest safe test is to run `setup-alarms.sh` with a very low threshold temporarily, or to stop the stack briefly (`dc stop api`) and see the uptime check fail within 15 minutes; then `dc start api`.

### Wording of this installation

`TERMINOLOGY_PROFILE` (Environment variable, not a secret; default `default`) selects the words and
web addresses from `frontend/src/terminology/profiles.json`, for example `church`. Change it in
GitHub, re-run `deploy-demo`, and the site serves the new words. Existing bookmarks to the old
addresses (for example `/organisation`) stop working after a change.

## 8. Security headers and limits

- Caddy adds HSTS, `nosniff`, a strict Content-Security-Policy (everything from the site's own origin), `X-Frame-Options: DENY`, a Permissions-Policy and removes the `Server` header. A page that suddenly breaks after a change may be blocked by the policy: open the browser developer console and look for "Content Security Policy" messages, then fix the page rather than loosening the policy.
- Login throttling: five failed passwords for the same email and account type from the same address lock that login for 15 minutes (HTTP 429). There is no general request rate limit at the proxy in the demo; production adds one at the edge (ADR-0012).
- Port 22 is open only to your addresses; ports 80 and 443 to the world.

## 9. Data tasks

Run these on the server in `/opt/skills` (see the [local guide](local-development.md) for what they create). The `tools` service gives the commands the demo password without exposing it to the running API:

```bash
dc run --rm -T tools python -m app.cli generate-demo-data --csv - --reset > demo-logins.csv   # umask 077 first
dc run --rm tools python -m app.cli create-admin --email you@example.com --mobile +971500000000
dc run --rm tools python -m app.cli seed-demo
```

Copy `demo-logins.csv` to your computer with `scp` and delete it from the server. It contains the shared demo password.

### Look at or edit the database with pgAdmin

pgAdmin runs as a container on the demo server, **only when you start it**, and listens on the server's own address (`127.0.0.1:5050`). You reach it through an SSH tunnel, so nothing new is open to the internet and the existing SSH rule (`TF_SSH_ALLOWED_CIDRS`) protects it.

One-time setup (GitHub → Settings → Environments → `demo`):
- Secret `PGADMIN_PASSWORD`: a long random password (16+ characters, no spaces). It is only the pgAdmin login.
- Optional variable `PGADMIN_EMAIL`: your login name, a real-looking address such as `you@yourdomain.com` (default `pgadmin4@pgadmin.org`).
- Re-run `deploy-demo` so the settings and `pgadmin-servers.json` reach the server.

Each time:
1. Start it on the server (as `deploy`):
   `cd /opt/skills && docker compose --env-file .env -f compose.demo.yml --profile pgadmin up -d pgadmin`
2. On your Mac, open the tunnel and leave it running:
   `ssh -i ~/.ssh/skills-deploy -N -L 5050:127.0.0.1:5050 deploy@13.127.253.202`
3. Open `http://localhost:5050` and log in with `PGADMIN_EMAIL` / `PGADMIN_PASSWORD`.
4. The server `skills (demo)` is already listed. Open it and enter the database password once. Copy it without showing it:
   `ssh -i ~/.ssh/skills-deploy deploy@13.127.253.202 "sed -n 's/^POSTGRES_PASSWORD=//p' /opt/skills/.env" | pbcopy`
5. When you are done, close the tunnel (Ctrl-C) and stop pgAdmin:
   `docker compose --env-file .env -f compose.demo.yml --profile pgadmin stop pgadmin`

Safety:
- For looking around, use a read-only login. On the server: `docker compose --env-file .env -f compose.demo.yml exec db psql -U skills -d skills -c "CREATE ROLE viewer LOGIN"`, then `... -c "\password viewer"` (type the password there), then `... -c "GRANT pg_read_all_data TO viewer"`. Add it as a second connection in pgAdmin.
- Before changing data, run `cd /opt/skills && ./backup.sh`. In pgAdmin turn auto-commit off (Query Tool toolbar), run your `UPDATE`, check the rows, then commit or roll back.
- Do not edit `password_hash` or tokens by hand. Reset passwords through the app and create admins with the CLI. Changes in pgAdmin bypass the app's checks.
- Never open port 5050 or 5432 in the Lightsail firewall.

## 10. Common problems

| Symptom | Likely cause and fix |
|---|---|
| Deploy stops at "Missing Environment setting" | A secret or variable is missing in the Environment `demo`; the log names it. |
| "Not authorized to perform sts:AssumeRoleWithWebIdentity" | The role trust does not match the token (repository IDs). Compare with `bootstrap/main.tf`; see ADR notes on the immutable subject. |
| Pre-deploy backup fails on reports | The reports folder must be group-readable by `deploy` (see `infra/README.md`). |
| Smoke test: TLS error on the first tries | Caddy is still obtaining the certificate; the test retries for about a minute. If it never succeeds, check DNS (`dig +short skills-demo.privatedir.in` must return `13.127.253.202`) and that port 80 is open. |
| Site shows a bad gateway | The `api` or `web` container is restarting: `dc ps`, `dc logs --tail=100 api`. |
| "DEMO_USER_PASSWORD must be strong and long enough" | The secret has fewer than 16 characters; update it and deploy. |
| Terraform plan wants to replace the instance | Stop. Do not apply. Compare the plan with the imported instance settings in `modules/lightsail_host`. |
| Disk nearly full | `docker image prune -af`; old backups are deleted from S3 automatically after 30 days. |

## Gemini pull request reviewer

Advisory review comment on each non-draft pull request from a branch in this repository (forks and Dependabot are skipped). It is not a required check. See [ADR-0013](adr/0013-gemini-agent-as-pull-request-reviewer.md).

- Secret: repository secret `GEMINI_API_KEY` (Settings > Secrets and variables > Actions). Never commit it or print it.
- Use a paid-tier or Vertex key so submitted code is not retained or used for model training (ADR-0013), and set a budget alert on the Google Cloud project.
- The model is set in the workflow (`GEMINI_MODEL`, default `gemini-2.5-flash`).
- Manual re-run: Actions > "Gemini Advisory PR Review" > Run workflow, with the PR number.
- Files: workflow `.github/workflows/gemini-pr-review.yml`, script `.github/scripts/review_agent.py` with tests `test_review_agent.py`, review brief `.github/review_context.md` (max 6000 characters; the script fails if it is missing or longer).
- The workflow checks out the base commit, so changes to the script or brief take effect after they are merged.
- Review skipped with a notice: the PR looks like it contains a secret (test files are not scanned by the reviewer; `ci-secrets` still covers them). Empty or failed model answers post nothing and fail the job.
