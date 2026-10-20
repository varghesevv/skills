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
