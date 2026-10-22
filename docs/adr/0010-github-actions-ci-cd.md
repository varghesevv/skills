# ADR-0010: GitHub Actions for CI/CD and GHCR for images

- **Status:** Proposed
- **Date:** 2026-10-20
- **Deciders:** Project owner

## Context

The code is on GitHub. We need automated tests on every pull request and automated deployment to the Lightsail demo.

## Decision

- **GitHub Actions** for CI (lint, type check, tests, migration check, security scans), infrastructure plan/apply, image build and deploy.
- Container images are built in CI and pushed to **GitHub Container Registry (GHCR)**, tagged with the commit SHA.
- Deploy connects to the Lightsail instance over **SSH** with a dedicated deploy key, pulls the new images and restarts with Docker Compose. Database migrations run as a one-off step before the new API starts.
- Test jobs run on **self-hosted runners**: the Raspberry Pi (Linux ARM64, label `pi`) and a Linux x64 machine whose runner itself runs inside a container. GitHub does not support `services:` containers on a runner that is already in a container, so the **backend** job (PostgreSQL as a service container) asks for `[self-hosted, pi]`. The **frontend** job needs only Node and asks for `[self-hosted, Linux]`, so either runner can take it. Lightweight jobs (docs links, secret scan, dependency audit) and the frontend `responsive` job (a real browser needs system libraries the self-hosted runners lack; it uses a mocked API and no secrets) use GitHub-hosted `ubuntu-latest`.
- Deployments use a GitHub **Environment** (`demo`) that holds secrets and can require approval.

## Alternatives considered

- AWS ECR: extra cost and credentials for no benefit here.
- AWS Systems Manager Run Command instead of SSH: cleaner (no open SSH port) but needs an agent and IAM setup on Lightsail; revisit later.
- Pulling from the server with Watchtower: less control, no migration step.

## Consequences

- No AWS credentials stored in GitHub for Terraform (OIDC); the deploy SSH key is the only server credential stored there.
- Rollback = redeploy a previous image tag.
- GitHub runner IPs change, so port 22 stays closed. The deploy job uses the OIDC role to open port 22 on the instance firewall for the runner's own IP only, deploys, then closes it again (always, even on failure). See infrastructure spec, section 7.
