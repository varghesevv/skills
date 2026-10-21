# 09 Infrastructure and CI/CD

Decision records: [ADR-0008](../adr/0008-aws-lightsail-single-instance-demo-deployment.md) (Lightsail), [ADR-0009](../adr/0009-terraform-for-infrastructure.md) (Terraform), [ADR-0010](../adr/0010-github-actions-ci-cd.md) (GitHub Actions). Database: PostgreSQL only ([ADR-0002](../adr/0002-postgresql-as-the-only-database.md)).

**Scope:** a **demo** environment on one AWS Lightsail instance. It is not production-grade (single point of failure). A production environment is planned within 1 to 2 months of the demo, so the demo must be built so that it can be reused or replaced cleanly (section 12). Production needs a new ADR.

**Fixed values (confirmed):**

| Item | Value |
|---|---|
| AWS region | `ap-south-1` (Mumbai); Lightsail availability zone `ap-south-1a` |
| Domain | `skills-demo.privatedir.com` (domain `privatedir.com` is registered in Route 53) |
| Public URL | `https://skills-demo.privatedir.com` (web at `/`, API at `/api/v1`) |

## 0. Current state (as of 2026-10-20)

The Lightsail instance was **created manually** by the owner before any Terraform existed:

| Item | Value |
|---|---|
| Size | 2 GB RAM, 2 vCPU, 60 GB SSD |
| IP address | 13.233.41.127 (must be confirmed as a Lightsail **static IP**; a default public IP changes when the instance is stopped and started) |
| Still to confirm | instance name, availability zone, operating system image, SSH key pair used, firewall rules, whether automatic snapshots are on |

Consequences for this spec:

- **Adopt, do not recreate.** Terraform will manage this instance by importing it (`terraform import`) into `envs/demo`, then bring the static IP, firewall rules, snapshot add-on, S3 backup bucket and Route 53 record under Terraform. Resource arguments in `modules/lightsail_host` must match the existing instance so the first `plan` shows no replacement (a replacement would destroy the server).
- **No separate data disk for the demo.** The 60 GB system SSD is enough for demo data, so PostgreSQL data lives on the instance disk under `/opt/skills/data` (Docker bind mounts). The separate `aws_lightsail_disk` in section 3 and `/mnt/skills-data` in sections 1 and 8 become optional and are deferred to production planning. Backups to S3 and snapshots matter more because a rebuilt instance loses the data.
- **Server bootstrap runs once over SSH** (install Docker, create the `deploy` user, directories, backup timer) instead of cloud-init, because user data cannot be applied to an existing instance. The same steps stay in `infra/scripts/bootstrap-server.sh` so the server is reproducible.

## 1. Target architecture

```
Internet
   |  80/443
[ Lightsail instance (static IP) ]  Ubuntu LTS + Docker + Compose
   |
   +-- proxy  (Caddy: HTTPS, routes / -> web, /api -> api)
   +-- web    (React build served by nginx or Caddy)
   +-- api    (FastAPI, uvicorn/gunicorn)
   +-- worker (APScheduler: scheduled reports)
   +-- db     (PostgreSQL 16, data on mounted Lightsail disk, NOT published to host)
   |
   +-- /mnt/skills-data/postgres   <- Lightsail block-storage disk
   +-- /mnt/skills-data/reports    <- generated report files

S3 bucket: nightly pg_dump + report files (optional)
GHCR: container images (api, web)
```

Rules:
- Only `proxy` publishes ports (80, 443). `db`, `api`, `worker` are on an internal Docker network.
- Firewall: 80 and 443 open to the world; 22 closed by default (see section 7).
- All containers `restart: unless-stopped`, have health checks, and log to the Docker JSON driver with size limits.

## 2. Repository additions

```
infra/
  terraform/
    bootstrap/          # run once manually: state bucket, GitHub OIDC provider and roles
    envs/
      demo/             # main.tf, variables.tf, outputs.tf, backend.tf, terraform.tfvars.example
    modules/
      lightsail_host/   # instance, static IP, disk, firewall, key pair
      backup_bucket/    # S3 bucket, lifecycle, IAM user/policy for backups
  docker/
    compose.demo.yml    # server compose file (images from GHCR)
    Caddyfile
    cloud-init.yaml     # installs Docker, mounts disk, creates /opt/skills, sets up cron/timers
  scripts/
    deploy.sh           # pull, migrate, up, health check, rollback hint
    backup.sh           # pg_dump -> gzip -> S3, prune old
    restore.sh          # restore from S3 dump
backend/Dockerfile
frontend/Dockerfile
docker-compose.yml      # local development (db, api, worker, web)
.github/
  workflows/
  dependabot.yml
  CODEOWNERS
  pull_request_template.md
```

## 3. Terraform requirements

- Terraform >= 1.10, AWS provider pinned (`~>` minor). `terraform fmt`, `validate`, `tflint` and `trivy config` must pass in CI.
- **Bootstrap** (manual, once): S3 bucket for Terraform state (versioned, encrypted, public access blocked), IAM OIDC provider for `token.actions.githubusercontent.com`, and two IAM roles trusted only for this repository: `skills-terraform` (plan/apply, limited to Lightsail, the state bucket and the backup bucket) and `skills-deploy` (only firewall open/close on the demo instance).
- **`envs/demo`** uses the S3 backend with `use_lockfile = true`.
- Resources (module `lightsail_host`):
  - `aws_lightsail_key_pair` (public key supplied as a variable; private key never in state)
  - `aws_lightsail_instance` (blueprint Ubuntu LTS, bundle >= 2 GB RAM, `user_data` = cloud-init)
  - `aws_lightsail_static_ip` and `aws_lightsail_static_ip_attachment`
  - `aws_lightsail_disk` and `aws_lightsail_disk_attachment` (PostgreSQL and report data, size variable, default 20 GB)
  - `aws_lightsail_instance_public_ports` (80, 443 open; 22 closed)
  - Automatic snapshot add-on enabled on the instance
- Module `backup_bucket`: `aws_s3_bucket` (private, versioning, encryption, lifecycle expiry 30 days), and an IAM user with a policy limited to that bucket (Lightsail instances cannot use instance roles; the access key is stored only on the server in `/opt/skills/.env`).
- Outputs: static IP, instance name, disk name, backup bucket name.
- Variables, not hard-coded values, for region (default `ap-south-1`), bundle size, domain name (`skills-demo.privatedir.com`), parent zone name (`privatedir.com`), SSH key, allowed admin CIDRs (Q13, to be supplied later; empty list means no manual SSH).
- No secrets in `.tfvars` committed to git. Only `terraform.tfvars.example`.
- **DNS (Terraform-managed):** look up the existing Route 53 hosted zone with `data "aws_route53_zone"` (name `privatedir.com`; the zone is NOT created or destroyed by this project) and create `aws_route53_record` `skills-demo` (type A, TTL 300) pointing to the Lightsail static IP. The `skills-terraform` role gets `route53:ChangeResourceRecordSets` and `route53:ListResourceRecordSets` limited to that hosted zone, and `route53:GetHostedZone`/`ListHostedZones`.
- Caddy obtains the Let's Encrypt certificate for `skills-demo.privatedir.com` automatically once the A record resolves (HTTP-01 on port 80, so port 80 must stay open). The domain registration itself must not be managed by Terraform.

## 4. Containers

- `backend/Dockerfile`: multi-stage, Python 3.12 slim, non-root user, dependencies pinned, `HEALTHCHECK` on `/health`. Same image runs `api` and `worker` with different commands.
- `frontend/Dockerfile`: build with Node LTS, serve static files with nginx (non-root where possible).
- Images tagged `ghcr.io/<owner>/skills-api:<git-sha>` and `skills-web:<git-sha>`, also `:demo` for the latest deployed.
- `docker-compose.yml` (local dev): `db` (PostgreSQL with named volume), `api` (hot reload), `worker`, `web` (Vite dev server). `docker compose up` must give a working app.
- `infra/docker/compose.demo.yml` (server): same services using GHCR images, `db` volume bound to `/mnt/skills-data/postgres`, health checks and `depends_on: condition: service_healthy`.

## 5. Configuration and secrets

| Setting | Where |
|---|---|
| `DATABASE_URL`, `POSTGRES_PASSWORD`, `JWT_SECRET`, `SMTP_*`, `CORS_ORIGINS`, `REPORT_TIMEZONE`, `BACKUP_BUCKET`, AWS backup key | GitHub Environment `demo` secrets/variables; deploy writes `/opt/skills/.env` (mode 600, owned by deploy user) |
| Terraform variables | `terraform.tfvars` locally (not committed) or GitHub Environment variables in CI |

Required GitHub repository secret for CI: `CI_DB_PASSWORD` (any random string; used for the throwaway test database). The application validates secrets at startup in `demo` and `prod` (ADR-0011).

Rules: `.env` and `*.tfvars` are git-ignored; secrets never appear in logs or images; rotating a secret = update GitHub secret and redeploy.

## 6. GitHub Actions workflows (`.github/workflows/`)

| Workflow | Trigger | Jobs |
|---|---|---|
| `ci-backend.yml` | PR and push touching `backend/**` | Python 3.12; install; `ruff` lint + format check; `mypy`; `pytest` with a **PostgreSQL 16 service container**; Alembic `upgrade head` then `downgrade base` check; OpenAPI schema export and diff; coverage report; `pip-audit` |
| `ci-frontend.yml` | PR and push touching `frontend/**` | Node LTS; install with lockfile; ESLint; Prettier check; `tsc --noEmit`; Vitest; build; `npm audit` (high only) |
| `ci-infra.yml` | PR touching `infra/**` | `terraform fmt -check`, `validate`, `tflint`, `trivy config`; `terraform plan` for `envs/demo` using OIDC role `skills-terraform`; plan posted as PR comment |
| `ci-secrets.yml` | every PR; push to `main` | `scripts/check-secrets.sh` and Gitleaks over the PR's commits (`--redact`); required check |
| `ci-docs.yml` | PR touching `docs/**` or `*.md` | Markdown lint and link check; verify ADR index lists every ADR file |
| `build-images.yml` | push to `main`; manual | Build `api` and `web` images with Buildx cache; scan with Trivy (fail on critical); push to GHCR with SHA tag |
| `terraform-apply.yml` | manual (`workflow_dispatch`) on `main`; Environment `demo` requires approval | `terraform apply` of the reviewed plan |
| `deploy-demo.yml` | after successful `build-images.yml` on `main`, or manual with a chosen image tag; Environment `demo` | See section 7 |
| `codeql.yml` | weekly and on PR | CodeQL for Python and JavaScript |

Branch protection on `main`: required status checks (`ci-backend`, `ci-frontend`, `ci-docs`, `ci-infra` where relevant), one approving review, no direct pushes, up-to-date branch before merge. `CODEOWNERS` assigns reviewers for `infra/`, `docs/adr/` and `backend/migrations/`. Dependabot updates for pip, npm, GitHub Actions, Docker and Terraform. All third-party actions pinned to a version (commit SHA preferred).

## 7. Deployment procedure (`deploy-demo.yml` and `deploy.sh`)

1. Assume AWS role `skills-deploy` through OIDC.
2. Open port 22 on the instance firewall for the runner's public IP only.
3. SSH to the instance with the deploy key (stored as an Environment secret).
4. Write/refresh `/opt/skills/.env` and `compose.demo.yml`, `Caddyfile`.
5. `docker compose pull` the new image tag.
6. Back up the database first (`backup.sh`).
7. Run migrations as a one-off container: `docker compose run --rm api alembic upgrade head`.
8. `docker compose up -d`; wait for health checks on `api` and `web`.
9. Smoke test: `GET /health` and `GET /api/v1/labels` through the public URL.
10. On failure: print logs, keep previous images, mark the job failed; rollback = rerun the workflow with the previous tag (migrations must be backward compatible for one release, or restore from the backup).
11. Always (even on failure): close port 22.

Concurrency group `deploy-demo` so two deploys never overlap.

## 8. Server bootstrap (cloud-init)

Installs Docker Engine and the Compose plugin, creates user `deploy` (docker group, key-only SSH), formats and mounts the data disk at `/mnt/skills-data` (persisted in `/etc/fstab`), creates `/opt/skills`, enables unattended security upgrades, configures log rotation, and installs a systemd timer for the nightly backup.

## 9. Backup, restore and monitoring

- **Nightly** `pg_dump` (custom format, gzip) uploaded to S3, kept 30 days (bucket lifecycle). Also run before every deploy.
- **Lightsail snapshots**: automatic daily snapshot add-on.
- **Restore** documented and tested: `restore.sh <s3-key>` into a fresh database; restore drill performed once before the demo is shared.
- **Monitoring (demo level):** Lightsail CPU and network alarms with email notification; disk usage alarm at 80%; external uptime check on `/health` (free tier of a monitoring service or a scheduled GitHub Action). Logs via `docker compose logs`; no central logging for the demo.

## 10. Security requirements for the environment

- HTTPS only; HTTP redirects to HTTPS (Caddy automatic certificates for `skills-demo.privatedir.com`).
- PostgreSQL not reachable from the internet; strong generated password.
- SSH: key only, root login disabled, port closed by default (section 7); manual admin access from allowed CIDRs only (Q13, owner will provide the list; until then no manual SSH, deploys use the temporary-IP method).
- IAM least privilege: the backup user can write only to the backup bucket; the deploy role can only change the instance firewall.
- Demo data only: no real personal data in the demo environment. Seed script provides fake users.
- Images scanned for vulnerabilities in CI; base images updated through Dependabot.

## 11. Acceptance criteria

- `terraform apply` from a clean AWS account (after bootstrap) creates the full environment, including the Route 53 record, with no manual console steps.
- `https://skills-demo.privatedir.com/health` returns OK with a valid certificate.
- A merge to `main` results in new images in GHCR and, after approval, a deployed demo with passing smoke test.
- A pull request cannot merge unless its relevant CI workflows pass.
- Killing the `db` container or rebooting the instance brings the system back with data intact.
- A backup can be restored into an empty database in under 15 minutes (documented drill).
- Teardown with `terraform destroy` removes billable resources (backup bucket protected by `prevent_destroy` unless explicitly overridden).

## 12. Path to production (planned within 1 to 2 months)

Build the demo so production is a configuration change, not a rewrite:

- Terraform layout supports more environments: `infra/terraform/envs/demo` now, `envs/prod` later. Shared modules take all environment-specific values as variables. No hard-coded names.
- Resource names, state keys, GitHub Environments (`demo`, later `prod`) and secrets are per environment.
- Production will probably replace single-instance PostgreSQL with a managed database (AWS RDS for PostgreSQL, Multi-AZ optional) and the Lightsail instance with a container service. This is decided by a new ADR before `envs/prod` is built. The application therefore must read only `DATABASE_URL` and keep no assumption that PostgreSQL is a local container.
- Keep images and migrations environment-independent: the same image tag that passed in demo is promoted to prod.
- Prepare a production checklist before go-live: separate AWS account or at least separate IAM roles, managed backups with point-in-time recovery, monitoring and alerting, log aggregation, WAF or rate limiting at the edge, domain (for example `skills.privatedir.com`), real SMTP provider, data protection review.
- The demo environment keeps fake data only and may be destroyed when production exists.
