#!/usr/bin/env bash
# List the database backups in the S3 backup bucket, newest last. Run on the server from
# /opt/skills. Uses the backup user's key from .env without printing it.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
get() { grep -E "^$1=" .env | head -n1 | cut -d= -f2-; }
bucket="$(get BACKUP_BUCKET)"
AWS_DEFAULT_REGION="$(get AWS_DEFAULT_REGION)"
AWS_ACCESS_KEY_ID="$(get AWS_ACCESS_KEY_ID)"
AWS_SECRET_ACCESS_KEY="$(get AWS_SECRET_ACCESS_KEY)"
export AWS_DEFAULT_REGION AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY

if [ -z "$bucket" ]; then
  echo "BACKUP_BUCKET is not set in .env" >&2
  exit 1
fi
aws s3 ls "s3://${bucket}/postgres/" --human-readable
