#!/bin/sh
# Creates or completes .env from .env.example. Idempotent: existing values are never changed.
# Missing keys are added with their default value; an empty POSTGRES_PASSWORD gets a random one.
# Prints key names only, never values.
set -eu
cd "$(dirname "$0")/.."
umask 077
touch .env

# Fill an empty POSTGRES_PASSWORD.
if grep -q '^POSTGRES_PASSWORD=$' .env; then
  password=$(openssl rand -hex 24)
  awk -v pw="$password" '/^POSTGRES_PASSWORD=$/ { print "POSTGRES_PASSWORD=" pw; next } { print }' \
    .env > .env.tmp && mv .env.tmp .env
  echo "Set POSTGRES_PASSWORD (generated, not shown)"
fi

# Add keys that are missing.
while IFS= read -r line; do
  case "$line" in ''|'#'*) continue ;; esac
  key=${line%%=*}
  if ! grep -q "^${key}=" .env; then
    value=${line#*=}
    if [ "$key" = "POSTGRES_PASSWORD" ]; then
      value=$(openssl rand -hex 24)
      echo "Added $key (generated, not shown)"
    else
      echo "Added $key"
    fi
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
done < .env.example

chmod 600 .env
echo ".env is complete."
