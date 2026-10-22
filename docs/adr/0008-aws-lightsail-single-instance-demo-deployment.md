# ADR-0008: AWS Lightsail single-instance deployment for the demo

- **Status:** Proposed
- **Date:** 2026-10-20
- **Deciders:** Project owner

## Context

We need a cheap, simple, public demo. The application (API, worker, web) and PostgreSQL will run as Docker containers. Traffic and data are small and the data is demo data.

## Decision

Deploy to **one AWS Lightsail Linux instance** with a static IP, running **Docker Compose** with services `proxy` (Caddy, automatic HTTPS), `web`, `api`, `worker` and `db` (PostgreSQL). PostgreSQL data lives on a separate **Lightsail block-storage disk** mounted into the instance. Nightly `pg_dump` backups go to an **S3 bucket**; Lightsail automatic snapshots are enabled as a second safety net.

## Alternatives considered

- **Lightsail managed database:** more reliable, but costs more and is not needed for a demo.
- **Lightsail containers service:** no persistent volumes for PostgreSQL, so the database would need to be external anyway.
- **ECS/Fargate + RDS:** the right target for production, too heavy and costly for a demo.
- **Kubernetes:** unnecessary for one small instance.

## Consequences

- Single point of failure: the instance. Acceptable for demo only; **not for production**. A new ADR will replace this when production is planned (likely RDS or managed PostgreSQL plus a container service).
- Deploys cause a short restart.
- Because the database runs in a container, backups and disk space are our responsibility; see the infrastructure specification.
- Instance needs at least 2 GB RAM for PostgreSQL and the API together.
- The owner plans a production environment within 1 to 2 months of the demo (confirmed 2026-10-20). Region is `ap-south-1` and the demo URL is `https://skills-demo.privatedir.in`. The application must stay portable (`DATABASE_URL` only) so moving to managed PostgreSQL is a configuration change. A follow-up ADR will decide the production architecture.
