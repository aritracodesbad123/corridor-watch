#!/usr/bin/env bash
# Create Corridor Watch Pub/Sub topics and the Cloud Run push subscription.
# Usage: ./scripts/setup_pubsub.sh [PROJECT_ID] [REGION]
set -euo pipefail

PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-corridor-watch-508420}}"
REGION="${2:-asia-southeast1}"
SERVICE="${SERVICE_NAME:-corridor-watch}"
TXN_TOPIC="${TRANSACTION_TOPIC:-corridor-transactions}"
INV_TOPIC="${INVESTIGATION_TOPIC:-corridor-investigations}"
SUB="${PUBSUB_PUSH_SUBSCRIPTION:-corridor-transactions-push}"

gcloud services enable pubsub.googleapis.com run.googleapis.com --project "$PROJECT_ID"

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
PUSH="${URL}/api/pubsub/push"

for TOPIC in "$TXN_TOPIC" "$INV_TOPIC"; do
  if gcloud pubsub topics describe "$TOPIC" --project "$PROJECT_ID" >/dev/null 2>&1; then
    echo "topic exists: $TOPIC"
  else
    gcloud pubsub topics create "$TOPIC" --project "$PROJECT_ID"
  fi
done

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud pubsub topics add-iam-policy-binding "$TXN_TOPIC" \
  --project "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/pubsub.publisher" \
  --quiet
gcloud pubsub topics add-iam-policy-binding "$INV_TOPIC" \
  --project "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/pubsub.publisher" \
  --quiet
gcloud pubsub topics add-iam-policy-binding "$TXN_TOPIC" \
  --project "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/pubsub.viewer" \
  --quiet

if gcloud pubsub subscriptions describe "$SUB" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "updating push endpoint on $SUB -> $PUSH"
  gcloud pubsub subscriptions update "$SUB" \
    --project "$PROJECT_ID" \
    --push-endpoint="$PUSH"
else
  gcloud pubsub subscriptions create "$SUB" \
    --project "$PROJECT_ID" \
    --topic="$TXN_TOPIC" \
    --push-endpoint="$PUSH" \
    --ack-deadline=60
fi

gcloud pubsub subscriptions add-iam-policy-binding "$SUB" \
  --project "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/pubsub.viewer" \
  --quiet

echo
echo "Topics: $TXN_TOPIC, $INV_TOPIC"
echo "Push:   $SUB -> $PUSH"
echo "Publisher SA: $RUNTIME_SA"
