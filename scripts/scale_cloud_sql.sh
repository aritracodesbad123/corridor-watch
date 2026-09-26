#!/usr/bin/env bash
# Keep Cloud SQL on the shared-core tier that fits the remaining credits.
# A load test can override: CW_SQL_TIER=db-custom-1-3840
# Causes a restart and brief downtime.
# Usage: ./scripts/scale_cloud_sql.sh [PROJECT_ID] [REGION]
set -euo pipefail

PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-corridor-watch-508420}}"
INSTANCE="${INSTANCE_NAME:-corridor-watch-pg}"
TIER="${CW_SQL_TIER:-db-f1-micro}"

echo "Patching $INSTANCE to ${TIER} (restart required)…"
gcloud sql instances patch "$INSTANCE" \
  --project "$PROJECT_ID" \
  --tier "$TIER" \
  --activation-policy=ALWAYS \
  --quiet

echo "Waiting until $INSTANCE is RUNNABLE…"
for _ in $(seq 1 60); do
  state="$(gcloud sql instances describe "$INSTANCE" --project "$PROJECT_ID" --format='value(state)')"
  echo "  state=$state"
  if [[ "$state" == "RUNNABLE" ]]; then
    tier="$(gcloud sql instances describe "$INSTANCE" --project "$PROJECT_ID" --format='value(settings.tier)')"
    echo "Cloud SQL ready: $tier"
    exit 0
  fi
  sleep 15
done
echo "Timed out waiting for Cloud SQL to become RUNNABLE" >&2
exit 1
