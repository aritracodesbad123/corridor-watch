#!/usr/bin/env bash
# Provision Cloud SQL Postgres and store DATABASE_URL in Secret Manager.
# Usage: ./scripts/setup_cloud_sql.sh [PROJECT_ID] [REGION]
set -euo pipefail

PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-corridor-watch-508420}}"
REGION="${2:-asia-southeast1}"
INSTANCE="${INSTANCE_NAME:-corridor-watch-pg}"
DB_NAME="${DB_NAME:-corridor_watch}"
DB_USER="${DB_USER:-corridor_app}"
SECRET_NAME="${DATABASE_URL_SECRET:-database-url}"

gcloud services enable sqladmin.googleapis.com secretmanager.googleapis.com --project "$PROJECT_ID"

if ! gcloud sql instances describe "$INSTANCE" --project "$PROJECT_ID" >/dev/null 2>&1; then
  ROOT_PASS="$(openssl rand -hex 16)"
  gcloud sql instances create "$INSTANCE" \
    --project "$PROJECT_ID" \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region "$REGION" \
    --storage-size=10GB \
    --availability-type=ZONAL \
    --root-password="$ROOT_PASS" \
    --quiet
fi

if ! gcloud sql databases describe "$DB_NAME" --instance "$INSTANCE" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud sql databases create "$DB_NAME" --instance "$INSTANCE" --project "$PROJECT_ID"
fi

APP_PASS="$(openssl rand -hex 16)"
if gcloud sql users list --instance "$INSTANCE" --project "$PROJECT_ID" --format='value(name)' | grep -qx "$DB_USER"; then
  gcloud sql users set-password "$DB_USER" --instance "$INSTANCE" --project "$PROJECT_ID" --password="$APP_PASS"
else
  gcloud sql users create "$DB_USER" --instance "$INSTANCE" --project "$PROJECT_ID" --password="$APP_PASS"
fi

CONNECTION="${PROJECT_ID}:${REGION}:${INSTANCE}"
# Unix socket URL used by Cloud Run's Cloud SQL integration.
DATABASE_URL="postgresql://${DB_USER}:${APP_PASS}@/${DB_NAME}?host=/cloudsql/${CONNECTION}"

if gcloud secrets describe "$SECRET_NAME" --project "$PROJECT_ID" >/dev/null 2>&1; then
  printf '%s' "$DATABASE_URL" | gcloud secrets versions add "$SECRET_NAME" --project "$PROJECT_ID" --data-file=-
else
  printf '%s' "$DATABASE_URL" | gcloud secrets create "$SECRET_NAME" --project "$PROJECT_ID" --data-file=-
fi

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --project "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/cloudsql.client" \
  --quiet
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/monitoring.viewer" \
  --quiet
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/run.viewer" \
  --quiet

echo "Cloud SQL ready: $CONNECTION"
echo "DATABASE_URL stored in Secret Manager as $SECRET_NAME"
