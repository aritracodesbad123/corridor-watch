#!/usr/bin/env bash
# Enable Cloud SQL backups + point-in-time recovery. Does not run a restore.
# Usage: ./scripts/enable_sql_pitr.sh PROJECT_ID [INSTANCE]
set -euo pipefail
PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-}}"
INSTANCE="${2:-${INSTANCE_NAME:-corridor-watch-pg}}"
if [[ -z "$PROJECT_ID" ]]; then
  echo "Usage: $0 PROJECT_ID [INSTANCE]" >&2
  exit 1
fi
gcloud sql instances patch "$INSTANCE" \
  --project "$PROJECT_ID" \
  --backup-start-time="${BACKUP_START:-18:00}" \
  --retained-backups-count="${RETAINED_BACKUPS:-7}" \
  --enable-point-in-time-recovery
echo "PITR requested. Confirm with ./scripts/dr_status.sh $PROJECT_ID $INSTANCE"
echo "A game day restore is still required before claiming RPO/RTO."
