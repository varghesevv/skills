#!/bin/sh
# Writes "run=true" or "run=false" to $GITHUB_OUTPUT: whether the mobile jobs have work to do.
# Pull requests that change nothing under mobile/ (or this workflow) finish early and succeed.
# Pushes to main always run. Usage: mobile-changed.sh <event_name> <base_ref>
set -eu
event="$1"
base="${2:-}"
run=true
if [ "$event" = "pull_request" ] && [ -n "$base" ]; then
  # The checkout has full history (fetch-depth: 0), so origin/<base> exists.
  if git diff --quiet "origin/$base...HEAD" -- mobile .github/workflows/ci-mobile.yml scripts/mobile-changed.sh scripts/check-dart-coverage.py docs/openapi.json 2>/dev/null; then
    run=false
  fi
fi
echo "mobile jobs run: $run"
echo "run=$run" >> "${GITHUB_OUTPUT:-/dev/null}"
