#!/usr/bin/env bash
# Run the backend tests against a throw-away PostgreSQL on a host without `docker compose`
# (for example the development container that shares the host's Docker daemon).
#
#   scripts/backend-tests-local.sh                 whole suite
#   scripts/backend-tests-local.sh -k ratings -v   extra arguments go to pytest
#
# A random password is generated for this run only. It lives in this process's environment, is not
# printed and is not written to any file. The database container is removed on exit.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
export CI_DB_PASSWORD="${CI_DB_PASSWORD:-$(openssl rand -hex 12)}"

# Capture the host and port instead of letting the helper print them to the terminal only.
out="$(bash "$root/scripts/ci-postgres.sh" start)"
trap 'bash "$root/scripts/ci-postgres.sh" stop' EXIT
host="$(printf '%s\n' "$out" | sed -n 's/^DB_HOST=//p')"
port="$(printf '%s\n' "$out" | sed -n 's/^DB_PORT=//p')"
echo "PostgreSQL ready at ${host}:${port}"

export DATABASE_URL="postgresql+psycopg://skills:${CI_DB_PASSWORD}@${host}:${port}/skills"
cd "$root/backend"
uv run pytest -q "$@"
