# Infrastructure

Demo environment on one AWS Lightsail instance. Specification: `docs/specification/09-infrastructure.md`. Day-to-day operation (deploy, rollback, backup drill, alarms): [`docs/operations-runbook.md`](../docs/operations-runbook.md).

## What is here

| Path | Purpose | Status |
|---|---|---|
| `docker/compose.demo.yml` | The stack on the server: proxy (Caddy), web, api, worker, db | phase 7b-1 |
| `docker/Caddyfile` | HTTPS, `/api` and `/health` to the api, everything else to the web image | phase 7b-1 |
| `docker/demo.env.example` | Checklist of what `/opt/skills/.env` must contain (no secrets) | phase 7b-1 |
| `scripts/bootstrap-server.sh` | One-time server setup over SSH (Docker, `deploy` user, folders, backup timer) | phase 7b-1 |
| `scripts/deploy.sh` | Pull, back up, migrate, start, wait for healthy | phase 7b-1 |
| `scripts/backup.sh`, `scripts/restore.sh`, `scripts/list-backups.sh` | Database backup to S3, restore, list the backups | phase 7b-1 |
| `scripts/setup-alarms.sh` | Creates the Lightsail alarms (run once by hand, needs an email address) | phase 8 |
| `terraform/bootstrap` | Run once by hand: state bucket, GitHub sign-in (OIDC) and the roles `skills-terraform` and `skills-deploy` | phase 7b-2 |
| `terraform/modules`, `terraform/envs/demo` | Lightsail host (adopted), static IP, firewall, daily snapshots, backup bucket and user, Route 53 record | phase 7b-2 |

## Setting up the server the first time

1. Generate a deploy key pair on your computer (`ssh-keygen -t ed25519 -f skills-deploy`). The private key goes into the GitHub Environment `demo` as a secret; the public key is given to the bootstrap script.
2. Copy `scripts/bootstrap-server.sh` to the server and run it as root:
   `DEPLOY_PUBLIC_KEY="$(cat skills-deploy.pub)" sudo -E bash bootstrap-server.sh`
3. Run the deploy workflow (phase 7b-3). It copies the compose file, Caddyfile and scripts to `/opt/skills`, writes `.env` from the GitHub Environment, and runs `deploy.sh`.

## What lives on the server

```
/opt/skills/
  .env                 secrets and settings, mode 600 (written by the deploy workflow)
  compose.demo.yml     Caddyfile   deploy.sh   backup.sh   restore.sh
  data/postgres        PostgreSQL data (bind mount)
  data/reports         generated report files (bind mount)
  data/downloads       test builds of the mobile app (read-only bind mount into the api)
```

Only Caddy publishes ports (80 and 443). The database is never reachable from outside the compose network.

## Backups

A systemd timer runs `backup.sh` every night at 02:30 UTC, and `deploy.sh` runs it before every deploy. Dumps go to `s3://<BACKUP_BUCKET>/postgres/`; report files to `.../reports/`. The bucket expires objects after 30 days.

Restore drill (safe while the demo is running, it restores into a separate database):

```
cd /opt/skills
aws s3 ls "s3://$BACKUP_BUCKET/postgres/"     # pick a key
./restore.sh postgres/skills-<timestamp>.dump
```

To replace the live database after a disaster: `CONFIRM_REPLACE=yes ./restore.sh <key> <live database name>`, then start the stack again.

## Secrets

Nothing secret is stored in this repository. The server's `.env` is written by the deploy workflow from GitHub Environment secrets (ADR-0011). Scripts read only the settings they need and never print them.

## Terraform: first-time runbook

You need an AWS CLI profile for an IAM user with administrator rights (not the root user) and Terraform 1.10 or newer on your computer (`brew install hashicorp/tap/terraform`). The `make tf-*` targets just call `terraform -chdir=...`.

```
export AWS_PROFILE=skills
make tf-lock                         # once: writes .terraform.lock.hcl; commit the result
```

1. **Bootstrap** (state bucket, GitHub sign-in, roles). Its own state stays in `terraform/bootstrap/terraform.tfstate` (git-ignored): keep a copy somewhere safe.
   ```
   make tf-init  TF_DIR=bootstrap
   make tf-plan  TF_DIR=bootstrap
   make tf-apply TF_DIR=bootstrap
   ```
   Then set these **repository variables** in GitHub (Settings, Secrets and variables, Actions, Variables), from the outputs: `TF_STATE_BUCKET`, `AWS_TERRAFORM_ROLE_ARN`, `AWS_DEPLOY_ROLE_ARN`. Create the GitHub Environment `demo` (with a required reviewer).
2. **Demo environment.** Copy `terraform/envs/demo/backend.hcl.example` to `backend.hcl` and `terraform.tfvars.example` to `terraform.tfvars`, and fill them in (your own address for SSH, the state bucket name).
   ```
   make tf-init TF_DIR=envs/demo TF_INIT_ARGS=-backend-config=backend.hcl
   make tf-plan TF_DIR=envs/demo
   ```
   Read the plan before applying:
   - The instance `skills` must show **no replacement** ("must be replaced" would destroy the server). A tag update and the snapshot add-on are expected.
   - A **new static IP** is created and attached. The instance gets a new public address (the old `13.233.41.127` is released), and the DNS record `skills-demo.privatedir.in` points to the new one.
   - The firewall opens 443, and port 22 is restricted to your `ssh_allowed_cidrs` plus the Lightsail console's browser SSH. Make sure your address is in `terraform.tfvars` first, or you lose SSH from your computer (the browser SSH still works).
   ```
   make tf-apply TF_DIR=envs/demo
   ```
3. **Backup user key.** Terraform creates the IAM user `skills-demo-backup` but not its access key, so that the secret never enters Terraform state. Create the key in the console (IAM, Users, Security credentials) and store it in the GitHub Environment `demo` secrets `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. Set the variable `BACKUP_BUCKET` from the `backup_bucket` output.
4. **Server bootstrap** over SSH, using the new static IP (see "Setting up the server the first time" above).

After this, pull requests that touch `infra/` get a plan as a comment, and `terraform-apply` (phase 7b-3) applies it after approval.

## Notes

- The Lightsail key pair `skills-demo` was created by hand and is only referenced by name, so its private key is never in Terraform state.
- `prevent_destroy` protects the backup and state buckets. To remove them on purpose, delete that line first.
- Trivy findings that are accepted on purpose go in `terraform/.trivyignore`, with a reason.

## Larger demo data set

`python -m app.cli generate-demo-data --csv <file> [--reset]` creates about 10 organisations
(8 approved, 1 pending, 1 rejected), 50 work hosts and 200 freelancers with varied skills,
skill levels, timings, languages and nativity, plus vouches, ratings and planned time off. All
accounts use the `DEMO_USER_PASSWORD` from the server's `.env`. The CSV (user_type, email,
password, name, status) is written owner-only; use `--csv -` to write to standard output and
redirect it into a file on the server:

    cd /opt/skills && umask 077
    docker compose --env-file .env -f compose.demo.yml run --rm -T tools \
      python -m app.cli generate-demo-data --csv - > demo-logins.csv

Copy it with `scp`, then delete it from the server. Never commit it. `--reset` removes the
earlier generated accounts (emails ending `@demo.example.com`) and creates them again.

### Fix for a server bootstrapped before the reports folder was group-readable

If the pre-deploy backup stops with "Skipping file /opt/skills/data/reports/. File/Directory is
not readable", run this once on the server as `deploy` (no sudo needed, Docker does the change):

    docker run --rm -v /opt/skills/data/reports:/r alpine \
      sh -c "chgrp -R $(id -g deploy) /r && chmod -R g+rX /r && chmod 750 /r"

## Notes on GitHub sign-in to AWS

GitHub can put the numeric owner and repository IDs into the OIDC subject (repository setting "immutable subject": `repo:owner@<id>/name@<id>:environment:demo`). The bootstrap roles trust both the legacy and the immutable form (`github_repository` and `github_repository_immutable` in `terraform/bootstrap/variables.tf`). If AWS answers "Not authorized to perform sts:AssumeRoleWithWebIdentity", compare the real subject with `gh api repos/<owner>/<repo>/actions/oidc/customization/sub` and update the variable.
