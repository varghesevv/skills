#!/usr/bin/env bash
# Restore a database backup from the S3 backup bucket.
#
#   ./restore.sh <s3-key> [target-database]
#
# <s3-key> is the name printed by backup.sh, for example postgres/skills-20261022T020000Z.dump.
# By default the dump goes into a NEW database named <POSTGRES_DB>_restore, which is safe to
# run while the demo is live, and is how the restore drill is done.
#
# To replace the live database (disaster recovery), give the live name as the target and set
# CONFIRM_REPLACE=yes. The api and worker are stopped first and must be started again after.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
COMPOSE=(docker compose --env-file .env -f compose.demo.yml)

if [ $# -lt 1 ]; then
  echo "Usage: $0 <s3-key> [target-database]" >&2
  exit 2
fi
key="$1"

get() { grep -E "^$1=" .env | head -n1 | cut -d= -f2-; }
bucket="$(get BACKUP_BUCKET)"
AWS_DEFAULT_REGION="$(get AWS_DEFAULT_REGION)"
AWS_ACCESS_KEY_ID="$(get AWS_ACCESS_KEY_ID)"
AWS_SECRET_ACCESS_KEY="$(get AWS_SECRET_ACCESS_KEY)"
export AWS_DEFAULT_REGION AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
db_user="$(get POSTGRES_USER)"
live_db="$(get POSTGRES_DB)"
target="${2:-${live_db}_restore}"

if [ -z "$bucket" ]; then
  echo "BACKUP_BUCKET is not set in .env" >&2
  exit 1
fi
if [[ ! "$target" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "Invalid database name: $target" >&2
  exit 2
fi

started="$(date +%s)"
if [ "$target" = "$live_db" ]; then
  if [ "${CONFIRM_REPLACE:-}" != "yes" ]; then
    echo "This replaces the live database '$live_db'. Run again with CONFIRM_REPLACE=yes to go on." >&2
    exit 2
  fi
  "${COMPOSE[@]}" stop api worker
fi

psql() { "${COMPOSE[@]}" exec -T db psql -U "$db_user" -d postgres -v ON_ERROR_STOP=1 "$@"; }
psql -c "DROP DATABASE IF EXISTS \"$target\" WITH (FORCE)"
psql -c "CREATE DATABASE \"$target\""

aws s3 cp "s3://${bucket}/${key}" - --only-show-errors \
  | "${COMPOSE[@]}" exec -T db pg_restore -U "$db_user" -d "$target" --no-owner --exit-on-error

echo "Restored $key into database '$target' in $(( $(date +%s) - started )) seconds."
"${COMPOSE[@]}" exec -T db psql -U "$db_user" -d "$target" -c \
  "SELECT 'freelancers' AS table_name, count(*) FROM freelancers UNION ALL SELECT 'organisations', count(*) FROM organisations UNION ALL SELECT 'work_hosts', count(*) FROM work_hosts" || true

if [ "$target" = "$live_db" ]; then
  echo "Start the application again: docker compose --env-file .env -f compose.demo.yml up -d"
fi
