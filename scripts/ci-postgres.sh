#!/usr/bin/env bash
# PostgreSQL for the backend CI job, started with plain `docker run`.
#
# Why not a `services:` container: GitHub refuses service containers on a runner that itself runs
# inside a container ("Container feature is not supported when runner is already running inside
# container"). This script works there and on a runner installed directly on a host.
#
#   scripts/ci-postgres.sh start   needs CI_DB_PASSWORD in the environment; writes DB_HOST and
#                                  DB_PORT to $GITHUB_ENV (or prints them when run by hand)
#   scripts/ci-postgres.sh stop    removes the container (safe to run twice)
#
# The password is passed to Docker by variable name, so it is never on a command line or in a log.
set -euo pipefail

IMAGE="postgres:16-alpine"
NAME="skills-ci-pg-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}-${GITHUB_JOB:-job}"

case "${1:-}" in
  start)
    : "${CI_DB_PASSWORD:?CI_DB_PASSWORD must be set}"
    docker rm -f "$NAME" >/dev/null 2>&1 || true

    mode=published
    network=""
    if [ -f /.dockerenv ]; then
      # The runner is a container: reach PostgreSQL over the runner container's own Docker network.
      # Its hostname is its container id unless it was started with --hostname; set
      # CI_RUNNER_CONTAINER then.
      runner="${CI_RUNNER_CONTAINER:-$(hostname)}"
      network="$(docker inspect "$runner" --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}' | awk '{print $1}')"
      if [ -z "$network" ]; then
        echo "::error::Could not find the Docker network of the runner container '$runner'. Set CI_RUNNER_CONTAINER to its name."
        exit 1
      fi
      if [ "$network" != "host" ]; then
        mode=network
      fi
    fi

    args=(--detach --name "$NAME" --env POSTGRES_USER=skills --env POSTGRES_DB=skills --env POSTGRES_PASSWORD)
    if [ "$mode" = network ]; then
      args+=(--network "$network")
    else
      args+=(--publish 127.0.0.1::5432)  # random free host port, never clashes with a dev database
    fi
    # The value comes from the environment variable of the same name.
    POSTGRES_PASSWORD="$CI_DB_PASSWORD" docker run "${args[@]}" "$IMAGE" >/dev/null

    ready=0
    for _ in $(seq 1 60); do
      if docker exec "$NAME" pg_isready -U skills -d skills >/dev/null 2>&1; then
        ready=1
        break
      fi
      sleep 1
    done
    if [ "$ready" -ne 1 ]; then
      echo "::error::PostgreSQL did not become ready within 60 seconds."
      docker logs --tail 20 "$NAME" 2>&1 | sed 's/^/postgres: /' || true
      docker rm -f "$NAME" >/dev/null 2>&1 || true
      exit 1
    fi

    if [ "$mode" = network ]; then
      host="$(docker inspect "$NAME" --format "{{(index .NetworkSettings.Networks \"$network\").IPAddress}}")"
      port=5432
    else
      host=127.0.0.1
      port="$(docker port "$NAME" 5432/tcp | head -1 | sed 's/.*://')"
    fi
    echo "PostgreSQL is ready at ${host}:${port} (${mode})"
    if [ -n "${GITHUB_ENV:-}" ]; then
      {
        echo "DB_HOST=${host}"
        echo "DB_PORT=${port}"
      } >> "$GITHUB_ENV"
    else
      echo "DB_HOST=${host}"
      echo "DB_PORT=${port}"
    fi
    ;;
  stop)
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    ;;
  *)
    echo "usage: $0 start|stop" >&2
    exit 2
    ;;
esac
