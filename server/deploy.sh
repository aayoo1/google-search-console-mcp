#!/usr/bin/env bash
# Deploy GSC MCP to Cloud Run. Run from this folder in Google Cloud Shell
# (or anywhere gcloud is installed and logged in). Safe to re-run.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project ID}"
REGION="${REGION:?Set REGION, e.g. us-central1}"
SERVICE="${SERVICE:-gsc-mcp}"
ALLOWED_DOMAIN="${ALLOWED_DOMAIN:?Set ALLOWED_DOMAIN to your Google Workspace domain}"
GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:?Set GOOGLE_CLIENT_ID from the new OAuth client}"
SA_NAME="${SERVICE}-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID" >/dev/null
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
BASE_URL="https://${SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app"

echo "== Enabling APIs"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com \
  firestore.googleapis.com searchconsole.googleapis.com

echo "== Firestore (stores sign-in sessions so restarts don't log people out)"
if ! gcloud firestore databases describe --database='(default)' >/dev/null 2>&1; then
  gcloud firestore databases create --location="$REGION" --type=firestore-native
fi

echo "== Service account"
if ! gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --display-name="GSC MCP"
fi
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" --role=roles/datastore.user --condition=None >/dev/null

echo "== Secrets"
make_secret() {  # name, value
  if ! gcloud secrets describe "$1" >/dev/null 2>&1; then
    printf '%s' "$2" | gcloud secrets create "$1" --data-file=- --replication-policy=automatic
  fi
  gcloud secrets add-iam-policy-binding "$1" \
    --member="serviceAccount:${SA_EMAIL}" --role=roles/secretmanager.secretAccessor >/dev/null
}
if ! gcloud secrets describe gsc-mcp-client-secret >/dev/null 2>&1; then
  read -rsp "Paste the OAuth client secret: " CLIENT_SECRET; echo
  make_secret gsc-mcp-client-secret "$CLIENT_SECRET"
else
  make_secret gsc-mcp-client-secret ""
fi
make_secret gsc-mcp-jwt-key "$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
make_secret gsc-mcp-storage-key "$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"

echo "== Deploying $SERVICE"
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --service-account "$SA_EMAIL" \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 3 \
  --set-env-vars "GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID},BASE_URL=${BASE_URL},ALLOWED_DOMAIN=${ALLOWED_DOMAIN},GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-secrets "GOOGLE_CLIENT_SECRET=gsc-mcp-client-secret:latest,JWT_SIGNING_KEY=gsc-mcp-jwt-key:latest,STORAGE_ENCRYPTION_KEY=gsc-mcp-storage-key:latest"

cat <<EOF

Done.
  1. In the OAuth client, add this Authorized redirect URI (if not already):
       ${BASE_URL}/auth/callback
  2. Add to Claude as a custom connector with URL:
       ${BASE_URL}/mcp
EOF
