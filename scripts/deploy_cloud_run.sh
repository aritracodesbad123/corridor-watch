#!/usr/bin/env bash
# Deploy Corridor Watch to Cloud Run with Secret Manager and Cloud SQL.
# Usage:
#   ./scripts/deploy_cloud_run.sh YOUR_PROJECT_ID [REGION]
# Do not raise max instances, concurrency, and pool size together.
# Measure the matrix in docs/COMPETITION_CLAIMS.md first.
set -euo pipefail

PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-}}"
REGION="${2:-asia-southeast1}"
SERVICE="${SERVICE_NAME:-corridor-watch}"
SECRET_NAME="${SECRET_NAME:-gemini-api-key}"
DB_SECRET="${DATABASE_URL_SECRET:-database-url}"
INSTANCE="${INSTANCE_NAME:-corridor-watch-pg}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "Usage: $0 PROJECT_ID [REGION]" >&2
  exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud is not installed. Install the Google Cloud SDK, then re-run." >&2
  echo "  brew install --cask google-cloud-sdk" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

gcloud config set project "$PROJECT_ID"
gcloud config set run/region "$REGION"

echo "Enabling required APIs…"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  pubsub.googleapis.com \
  sqladmin.googleapis.com \
  monitoring.googleapis.com \
  aiplatform.googleapis.com \
  --project "$PROJECT_ID"

if ! gcloud secrets describe "$SECRET_NAME" --project "$PROJECT_ID" >/dev/null 2>&1; then
  if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    echo "Secret $SECRET_NAME does not exist. Export GEMINI_API_KEY and re-run." >&2
    exit 1
  fi
  printf '%s' "$GEMINI_API_KEY" | gcloud secrets create "$SECRET_NAME" \
    --project "$PROJECT_ID" \
    --data-file=-
else
  if [[ -n "${GEMINI_API_KEY:-}" ]]; then
    printf '%s' "$GEMINI_API_KEY" | gcloud secrets versions add "$SECRET_NAME" \
      --project "$PROJECT_ID" \
      --data-file=-
  fi
fi

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --project "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet

SECRET_FLAGS="GEMINI_API_KEY=${SECRET_NAME}:latest"
USERS_SECRET="${USERS_SECRET:-console-users}"
USERS_FILE="$ROOT/credentials.json"
if [[ ! -f "$USERS_FILE" ]]; then
  USERS_FILE="$ROOT/credentials.example.json"
fi
if [[ -f "$USERS_FILE" ]]; then
  if gcloud secrets describe "$USERS_SECRET" --project "$PROJECT_ID" >/dev/null 2>&1; then
    if [[ -n "${UPDATE_CONSOLE_USERS:-}" ]]; then
      gcloud secrets versions add "$USERS_SECRET" --project "$PROJECT_ID" --data-file="$USERS_FILE"
    fi
  else
    gcloud secrets create "$USERS_SECRET" --project "$PROJECT_ID" --data-file="$USERS_FILE"
  fi
  gcloud secrets add-iam-policy-binding "$USERS_SECRET" \
    --project "$PROJECT_ID" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet
  SECRET_FLAGS="${SECRET_FLAGS},CORRIDOR_WATCH_USERS=${USERS_SECRET}:latest"
fi
CLOUDSQL_FLAGS=()
if gcloud secrets describe "$DB_SECRET" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud secrets add-iam-policy-binding "$DB_SECRET" \
    --project "$PROJECT_ID" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet
  SECRET_FLAGS="${SECRET_FLAGS},DATABASE_URL=${DB_SECRET}:latest"
  CLOUDSQL_FLAGS+=(--add-cloudsql-instances="${PROJECT_ID}:${REGION}:${INSTANCE}")
fi

# Sized for Cloud SQL custom-2-7680 (~200 connections).
# 10 replicas × (pool 8 + overflow 4) = 120 connections.
CPU="${CW_CPU:-2}"
MEMORY="${CW_MEMORY:-2Gi}"
MIN_INSTANCES="${CW_MIN_INSTANCES:-2}"
MAX_INSTANCES="${CW_MAX_INSTANCES:-10}"
CONCURRENCY="${CW_CONCURRENCY:-16}"
echo "Deploying $SERVICE to Cloud Run ($REGION) cpu=${CPU} mem=${MEMORY} min=${MIN_INSTANCES} max=${MAX_INSTANCES} concurrency=${CONCURRENCY}…"
gcloud run deploy "$SERVICE" \
  --source "$ROOT" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory "$MEMORY" \
  --cpu "$CPU" \
  --timeout 300 \
  --min-instances "$MIN_INSTANCES" \
  --max-instances "$MAX_INSTANCES" \
  --concurrency "$CONCURRENCY" \
  --no-cpu-throttling \
  --set-env-vars "ENVIRONMENT=gcp,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},REGION=${REGION},GEMINI_BACKEND=vertex,VERTEX_LOCATION=global,GEMINI_MODEL=${GEMINI_MODEL:-gemini-3.6-flash},TRANSACTION_TOPIC=corridor-transactions,INVESTIGATION_TOPIC=corridor-investigations,PUBSUB_PUSH_SUBSCRIPTION=corridor-transactions-push,CW_PG_POOL_MAX=${CW_PG_POOL_MAX:-8},CW_PG_OVERFLOW=${CW_PG_OVERFLOW:-4},CW_INGEST_SLOTS=${CW_INGEST_SLOTS:-8},CW_SKIP_INVESTIGATION_NOTIFY=${CW_SKIP_INVESTIGATION_NOTIFY:-true}" \
  --set-secrets "$SECRET_FLAGS" \
  "${CLOUDSQL_FLAGS[@]}"

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
echo
echo "Deployed: $URL"
echo "Health:   $URL/api/health"
