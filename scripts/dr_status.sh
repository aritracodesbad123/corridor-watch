#!/usr/bin/env bash
# Read Cloud SQL backup/PITR and Pub/Sub retention. Does not restore anything.
# Usage: ./scripts/dr_status.sh [PROJECT_ID] [INSTANCE] [REGION]
set -euo pipefail
PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-}}"
INSTANCE="${2:-${INSTANCE_NAME:-corridor-watch-pg}}"
REGION="${3:-${REGION:-asia-southeast1}}"
if [[ -z "$PROJECT_ID" ]]; then
  echo "Usage: $0 PROJECT_ID [INSTANCE] [REGION]" >&2
  exit 1
fi
echo "=== Cloud SQL $INSTANCE ==="
gcloud sql instances describe "$INSTANCE" --project "$PROJECT_ID" --format='yaml(settings.backupConfiguration,name,state,gceZone)'
echo
echo "=== Pub/Sub corridor-transactions ==="
gcloud pubsub topics describe corridor-transactions --project "$PROJECT_ID" --format='yaml(name,messageRetentionDuration)' || true
echo
echo "RPO/RTO remain TARGET until a restore game day is measured. Do not invent timings."
