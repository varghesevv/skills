# Infrastructure

Demo environment on one AWS Lightsail instance. Specification: `docs/specification/09-infrastructure.md`.

## What is here

| Path | Purpose | Status |
|---|---|---|
| `docker/compose.demo.yml` | The stack on the server: proxy (Caddy), web, api, worker, db | phase 7b-1 |
| `docker/Caddyfile` | HTTPS, `/api` and `/health` to the api, everything else to the web image | phase 7b-1 |
| `docker/demo.env.example` | Checklist of what `/opt/skills/.env` must contain (no secrets) | phase 7b-1 |
| `scripts/bootstrap-server.sh` | One-time server setup over SSH (Docker, `deploy` user, folders, backup timer) | phase 7b-1 |
| `scripts/deploy.sh` | Pull, back up, migrate, start, wait for healthy | phase 7b-1 |
| `scripts/backup.sh`, `scripts/restore.sh` | Database backup to S3 and restore | phase 7b-1 |
| `terraform/` | Lightsail host, static IP, firewall, backup bucket, Route 53 record | phase 7b-2 |

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
