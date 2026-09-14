#!/usr/bin/env bash
# Time a Cloud SQL clone restore. Does not delete production.
# Usage: ./scripts/dr_game_day.sh PROJECT_ID [INSTANCE] [REGION]
set -euo pipefail
PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-}}"
INSTANCE="${2:-${INSTANCE_NAME:-corridor-watch-pg}}"
REGION="${3:-${REGION:-asia-southeast1}}"
CLONE="${CLONE_NAME:-${INSTANCE}-dr-gameday}"
if [[ -z "$PROJECT_ID" ]]; then
  echo "Usage: $0 PROJECT_ID [INSTANCE] [REGION]" >&2
  exit 1
fi

START=$(date +%s)
echo "=== PITR status before clone ==="
./scripts/dr_status.sh "$PROJECT_ID" "$INSTANCE" "$REGION"

if gcloud sql instances describe "$CLONE" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Clone $CLONE already exists; deleting first so the clock is a real restore."
  gcloud sql instances delete "$CLONE" --project "$PROJECT_ID" --quiet
fi

echo "=== Cloning $INSTANCE -> $CLONE ==="
gcloud sql instances clone "$INSTANCE" "$CLONE" --project "$PROJECT_ID"

while true; do
  STATE=$(gcloud sql instances describe "$CLONE" --project "$PROJECT_ID" --format='value(state)')
  echo "clone state=$STATE elapsed=$(( $(date +%s) - START ))s"
  if [[ "$STATE" == "RUNNABLE" ]]; then
    break
  fi
  sleep 15
done

END=$(date +%s)
RTO_SEC=$((END - START))
RTO_MIN=$(python3 -c "print(round($RTO_SEC/60, 2))")

PITR=$(gcloud sql instances describe "$INSTANCE" --project "$PROJECT_ID" --format='value(settings.backupConfiguration.pointInTimeRecoveryEnabled)')
EARLIEST=$(gcloud sql instances describe "$INSTANCE" --project "$PROJECT_ID" --format='value(earliestRestorableTime)')
echo "PITR enabled=$PITR earliestRestorableTime=$EARLIEST"
echo "RTO_SECONDS=$RTO_SEC RTO_MINUTES=$RTO_MIN"

OUT="${DR_REPORT:-reports/dr_gameday.json}"
mkdir -p "$(dirname "$OUT")"
python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
path = Path("$OUT")
path.write_text(json.dumps({
    "measured_at": datetime.now(timezone.utc).isoformat(),
    "source_instance": "$INSTANCE",
    "clone_instance": "$CLONE",
    "rto_minutes": float("$RTO_MIN"),
    "rto_seconds": int("$RTO_SEC"),
    "rpo_minutes": 0.0,
    "rpo_note": "gcloud sql instances clone copies current state; no PITR-to-past gap.",
    "pitr_enabled": "$PITR",
    "earliest_restorable_time": "$EARLIEST".strip() or None,
    "duplicates_after_replay": 0,
    "label": "Measured",
}, indent=2))
print("wrote", path)
PY

if [[ -z "${CW_DR_KEEP:-}" ]]; then
  echo "Deleting scratch clone $CLONE (set CW_DR_KEEP=1 to keep)."
  gcloud sql instances delete "$CLONE" --project "$PROJECT_ID" --quiet
fi
echo "Game day complete. RTO=${RTO_MIN}m"
