# ADR-0003: Python FastAPI backend with SQLAlchemy and Alembic

- **Status:** Proposed
- **Date:** 2026-10-20
- **Deciders:** Project owner

## Context

The backend must be written in Python and provide a REST API for a React web app and a future mobile app. We want typed request validation, automatic API documentation, and a client generator for the frontend.

## Decision

- Python 3.12 with **FastAPI** and **Pydantic v2**.
- **SQLAlchemy 2.0** for data access and **Alembic** for migrations.
- OpenAPI schema is the contract between backend and clients.

## Alternatives considered

- Django + DRF: more built in (admin, ORM), heavier, less natural for a typed OpenAPI-first API.
- Flask: more manual wiring for validation and docs.

## Consequences

- OpenAPI is generated automatically; the frontend generates a typed client from it.
- We write our own auth and admin pieces (no Django admin).
- Async support available; keep to simple, well-tested patterns.
