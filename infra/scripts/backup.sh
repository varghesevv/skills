#!/usr/bin/env bash
# Back up the database (and the report files) to the S3 backup bucket.
# Run on the server from /opt/skills, by the nightly timer and before every deploy.
# Bucket lifecycle rules delete backups after 30 days.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
COMPOSE=(docker compose --env-file .env -f compose.demo.yml)

# Read only the settings this script needs; never print them.
get() { grep -E "^$1=" .env | head -n1 | cut -d= -f2-; }
bucket="$(get BACKUP_BUCKET)"
AWS_DEFAULT_REGION="$(get AWS_DEFAULT_REGION)"
AWS_ACCESS_KEY_ID="$(get AWS_ACCESS_KEY_ID)"
AWS_SECRET_ACCESS_KEY="$(get AWS_SECRET_ACCESS_KEY)"
export AWS_DEFAULT_REGION AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
db_user="$(get POSTGRES_USER)"
db_name="$(get POSTGRES_DB)"

if [ -z "$bucket" ]; then
  echo "BACKUP_BUCKET is not set in .env" >&2
  exit 1
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
key="postgres/skills-${stamp}.dump"

# Custom format is already compressed and restores with pg_restore.
"${COMPOSE[@]}" exec -T db pg_dump -U "$db_user" -d "$db_name" -Fc \
  | aws s3 cp - "s3://${bucket}/${key}" --only-show-errors

# Report files are copied too (small; the report history in the database points to them).
if [ -d data/reports ]; then
  aws s3 sync data/reports "s3://${bucket}/reports/" --only-show-errors
fi

echo "Backup written: s3://${bucket}/${key}"
