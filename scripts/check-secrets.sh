#!/bin/sh
# Fails when the repository contains likely secrets. Run locally, as a git hook and in CI.
# Prints only "file:line  rule", never the matching text, so a secret cannot end up in a log.
# To allow a line that is not a secret (for example a test placeholder), add: secret-scan:allow
set -u
cd "$(git rev-parse --show-toplevel)"
status=0

fail() { echo "SECRET CHECK FAILED  $1  ($2)"; status=1; }

# 1. Files that must never be committed.
for f in $(git ls-files --cached --others --exclude-standard); do
  case "$f" in
    .env|*/.env|*.tfvars|*.pem|*.p12|*.pfx|*.key|id_rsa|id_ed25519|*.tfstate|*.tfstate.*|\
    *.jks|*.keystore|key.properties|*/key.properties|google-services.json|*/google-services.json|\
    GoogleService-Info.plist|*/GoogleService-Info.plist|*firebase-adminsdk*.json)
      fail "$f" "file type must not be committed" ;;
  esac
done

# 2. Content rules. git grep searches tracked and untracked (not ignored) text files.
scan() { # $1 = rule name, $2 = extended regex, $3 = extra grep flags
  git grep -I -n -E $3 --untracked -e "$2" -- . \
      ':!scripts/check-secrets.sh' ':!*package-lock.json' ':!*uv.lock' 2>/dev/null |
    grep -v 'secret-scan:allow' | cut -d: -f1,2 |
    while IFS= read -r hit; do fail "$hit" "$1"; done
}

hits=$(
  scan "URL with an inline password" \
    '[a-zA-Z][a-zA-Z0-9+.-]*://[^[:space:]:/@$]+:[^[:space:]@$%{}<>*]+@' "" ;
  scan "quoted secret assignment" \
    '(password|passwd|secret|token|api_?key)[a-z_]*["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"'$[:space:]{]{6,}["'"'"']' "-i" ;
  scan "unquoted secret assignment" \
    '^[[:space:]]*[A-Z_]*(PASSWORD|PASSWD|SECRET|TOKEN|API_KEY)[A-Z_]*[[:space:]]*[:=][[:space:]]*[A-Za-z0-9/+_.!@#%^&*-]{6,}[[:space:]]*$' "" ;
  scan "AWS access key id" 'AKIA[0-9A-Z]{16}' "" ;
  scan "private key block" '-----BEGIN [A-Z ]*PRIVATE KEY-----' "" ;
  scan "GitHub token" 'gh[pousr]_[A-Za-z0-9]{30,}' ""
)
if [ -n "$hits" ]; then
  echo "$hits"
  status=1
fi

if [ "$status" -ne 0 ]; then
  echo
  echo "Secrets must come from environment variables or GitHub secrets, never from files in git."
  echo "See docs/adr/0011-secrets-from-environment-only.md"
else
  echo "Secret check passed."
fi
exit "$status"
