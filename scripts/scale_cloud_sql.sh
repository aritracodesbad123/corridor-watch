#!/usr/bin/env bash
# Raise Cloud SQL off db-f1-micro. Causes a restart and brief downtime.
# Usage: ./scripts/scale_cloud_sql.sh [PROJECT_ID] [REGION]
set -euo pipefail

PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-corridor-watch-508420}}"
INSTANCE="${INSTANCE_NAME:-corridor-watch-pg}"
# 2 vCPU / 7.5 GiB. Default max_connections is ~200 — enough for
# 10 Cloud Run replicas × (pool 8 + overflow 4).
CPU="${CW_SQL_CPU:-2}"
MEMORY="${CW_SQL_MEMORY:-7680MB}"

echo "Patching $INSTANCE to ${CPU} vCPU / ${MEMORY} (restart required)…"
gcloud sql instances patch "$INSTANCE" \
  --project "$PROJECT_ID" \
  --cpu "$CPU" \
  --memory "$MEMORY" \
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
