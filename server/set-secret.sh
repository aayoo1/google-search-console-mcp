#!/usr/bin/env bash
# Replace the OAuth client secret used by the GSC MCP, then restart it.
#
#   ./set-secret.sh client_secret_XXXX.json   # read it from the downloaded JSON (easiest)
#   ./set-secret.sh                           # or paste the GOCSPX-... value when asked
#
# The secret is never printed. Quotes, commas and spaces around a pasted value
# are stripped, and nothing is saved unless it looks like a real client secret.
set -euo pipefail
REGION="${REGION:?Set REGION to the Cloud Run region}"
SERVICE="${SERVICE:-gsc-mcp}"
SECRET_NAME="${SECRET_NAME:-gsc-mcp-client-secret}"

if [[ $# -ge 1 ]]; then
  S=$(python3 - "$1" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
print((d.get("web") or d.get("installed") or d)["client_secret"])
EOF
)
else
  read -rsp "Paste the client secret (GOCSPX-...), then Enter: " S; echo
fi

# Strip whitespace, quotes and trailing commas picked up when copying from JSON.
S=$(printf '%s' "$S" | tr -d '[:space:]"'"'"',')

# Pasting twice (easy when nothing shows on screen) doubles the value.
half=$(( ${#S} / 2 ))
if (( ${#S} % 2 == 0 )) && [[ ${S:0:half} == "${S:half}" ]]; then
  echo "(It was pasted twice - using one copy.)"
  S=${S:0:half}
fi

if [[ ! $S =~ ^GOCSPX-[A-Za-z0-9_-]{20,40}$ ]]; then
  echo "NOT SAVED: that doesn't look like a single client secret (expected GOCSPX- plus ~28 letters/numbers, pasted once)."
  exit 1
fi
echo "Looks valid (${#S} characters). Saving..."
printf '%s' "$S" | gcloud secrets versions add "$SECRET_NAME" --data-file=- >/dev/null
unset S
echo "Saved. Restarting $SERVICE so it uses the new secret..."
gcloud run services update "$SERVICE" --region "$REGION" \
  --update-env-vars "SECRET_UPDATED=$(date +%s)" --quiet >/dev/null
echo "Done. Click Connect in Claude again."
