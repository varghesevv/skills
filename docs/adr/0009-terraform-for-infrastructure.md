# ADR-0009: Terraform for infrastructure

- **Status:** Proposed
- **Date:** 2026-10-20
- **Deciders:** Project owner

## Context

Several contributors will touch infrastructure. Click-built servers cannot be reviewed, repeated or recovered.

## Decision

Define all AWS resources in **Terraform** under `infra/terraform/`. Remote state in an **S3 bucket** with native state locking (`use_lockfile`), created once by a small bootstrap configuration. GitHub Actions authenticates to AWS with **OIDC** (no long-lived AWS keys in GitHub).

## Alternatives considered

- AWS CloudFormation/CDK: AWS-only, heavier for this size.
- Manual console setup: not reproducible or reviewable.

## Consequences

- Infrastructure changes go through pull requests with a visible `terraform plan`.
- Terraform version and provider versions are pinned.
- The bootstrap step (state bucket, OIDC role) is run manually once by the owner.
