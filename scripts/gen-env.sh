#!/bin/sh
# Creates or completes .env from .env.example. Idempotent: existing values are never changed.
# Missing keys are added with their default value; empty generated secrets get a random value.
# Prints key names only, never values.
set -eu
cd "$(dirname "$0")/.."
umask 077
touch .env

# Secrets that are generated here when empty or missing.
GENERATED="POSTGRES_PASSWORD JWT_SECRET DEMO_USER_PASSWORD"

# Fill generated secrets that exist but are empty.
for key in $GENERATED; do
  if grep -q "^${key}=$" .env; then
    value=$(openssl rand -hex 24)
    awk -v k="$key" -v v="$value" 'BEGIN { p = k "=" } $0 == p { print p v; next } { print }' \
      .env > .env.tmp && mv .env.tmp .env
    echo "Set $key (generated, not shown)"
  fi
done

# Add keys that are missing.
while IFS= read -r line; do
  case "$line" in ''|'#'*) continue ;; esac
  key=${line%%=*}
  if ! grep -q "^${key}=" .env; then
    value=${line#*=}
    case " $GENERATED " in
      *" $key "*)
        value=$(openssl rand -hex 24)
        echo "Added $key (generated, not shown)" ;;
      *) echo "Added $key" ;;
    esac
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
done < .env.example

chmod 600 .env
echo ".env is complete."
