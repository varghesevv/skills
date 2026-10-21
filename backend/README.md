# Skills backend

FastAPI + SQLAlchemy 2 + Alembic on PostgreSQL. See `docs/specification/` at the repository root.

```bash
uv sync                      # install (Python 3.12)
docker compose up -d db      # from the repo root: PostgreSQL
export DATABASE_URL=postgresql+psycopg://skills:skills@localhost:5432/skills
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run pytest                # DB tests run when DATABASE_URL is set
uv run ruff check . && uv run ruff format --check . && uv run mypy app
```

## Database tests

`uv run pytest` runs the database tests when `DATABASE_URL` points at a PostgreSQL server whose user may
create databases. The tests create and use their own databases (`skills_test`, `skills_migration_test`) and
never touch the development database. If you edit a migration that you already ran, drop them:
`docker compose exec db psql -U skills -d postgres -c 'DROP DATABASE skills_test' -c 'DROP DATABASE skills_migration_test'`.

New migration after changing a model: `uv run alembic revision --autogenerate -m "describe change"`, then review it
(Alembic does not detect trigger, exclusion or CHECK changes). `tests/test_migrations.py` fails if models and
migrations drift apart.
