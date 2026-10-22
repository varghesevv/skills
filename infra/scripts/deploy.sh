#!/usr/bin/env bash
# Deploy the demo stack on the server. Run as the `deploy` user from /opt/skills, after the
# deploy workflow has written .env, compose.demo.yml and Caddyfile there.
#
#   ./deploy.sh
#
# Steps: pull images, back up the database, migrate, start, wait until healthy.
# Rollback: deploy again with the previous IMAGE_TAG (printed below). Migrations must stay
# backward compatible for one release; otherwise restore the backup with restore.sh.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

# Lightsail has no disk metric, so check here: refuse to deploy onto an almost full disk.
used="$(df --output=pcent /opt/skills | tail -n1 | tr -dc '0-9')"
if [ "${used:-0}" -ge 90 ]; then
  echo "Disk is ${used}% full. Free space first (docker image prune -af, old logs, old backups)." >&2
  exit 1
fi
echo "Disk usage: ${used}%"
COMPOSE=(docker compose --env-file .env -f compose.demo.yml)

if [ ! -f .env ]; then
  echo "Missing .env in $(pwd)" >&2
  exit 1
fi

# Read the tag without sourcing the file, so nothing else in it is ever printed or executed.
current_tag="$(grep -E '^IMAGE_TAG=' .env | head -n1 | cut -d= -f2-)"
previous_tag="$(cat .deployed_tag 2>/dev/null || true)"
echo "Deploying image tag: ${current_tag:-unknown} (previous: ${previous_tag:-none})"

"${COMPOSE[@]}" pull

# Back up first, but only when a database is already running (the very first deploy has none).
if [ "${SKIP_BACKUP:-0}" != "1" ] && "${COMPOSE[@]}" ps --status running --services 2>/dev/null | grep -qx db; then
  ./backup.sh
else
  echo "No running database (or SKIP_BACKUP=1): skipping the pre-deploy backup."
fi

# Migrations run in a one-off container; compose starts the database first and waits for it.
"${COMPOSE[@]}" run --rm api alembic upgrade head

"${COMPOSE[@]}" up -d --remove-orphans --wait --wait-timeout 180

# A changed Caddyfile is a mounted file, so compose does not recreate the proxy for it: reload.
if ! "${COMPOSE[@]}" exec -T proxy caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
  echo "Caddy reload failed; restarting the proxy."
  "${COMPOSE[@]}" restart proxy
fi

echo "$current_tag" > .deployed_tag
echo "Deployed. To roll back, deploy the previous tag: ${previous_tag:-none}"
docker image prune -f >/dev/null
