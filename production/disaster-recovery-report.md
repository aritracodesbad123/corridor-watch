# Disaster-recovery report

**Status:** Game day timed 2026-09-14. Artifact: `reports/dr_gameday.json`.

## Objectives

| Objective | Target | Measured |
|---|---|---|
| RPO | ≤ 5 minutes | **0 min** (current-state `gcloud sql instances clone`) |
| RTO | ≤ 30 minutes | **4.5 min** (270s clone to RUNNABLE) |

Do not treat Cloud Run restart or a local `fraud_demo.db` copy as a DR drill.

## What the architecture can recover from (design)

```
Cloud SQL  → automated backups → point-in-time recovery
Pub/Sub    → topic retention + idempotent redelivery
Audit log  → append-only rows in PostgreSQL
Outbox     → unpublished notify rows retry after commit
Queue      → CLAIMED/RETRY/DEAD_LETTER survive worker death
```

Idempotency is `(source_system, source_event_id)` plus `message_id`. Replay after restore must ACK duplicates, not double-queue.

## Enable / inspect (does not restore)

```bash
./scripts/enable_sql_pitr.sh YOUR_PROJECT_ID    # backups + PITR
./scripts/dr_status.sh YOUR_PROJECT_ID          # read backupConfiguration
```

Confirm in the `dr_status.sh` dump:

- `enabled: true` on backups
- point-in-time recovery enabled
- a retention / earliest restorable time field

Pub/Sub: `gcloud pubsub topics describe corridor-transactions --format='yaml(messageRetentionDuration)'`

## Game-day protocol (run 2026-09-14)

1. Snapshot `dr_status.sh` output and current `/api/ledger-stats`.
2. Create a Cloud SQL clone (or PITR clone) — do **not** delete production in a competition demo unless you have a second instance.
3. Point a scratch Cloud Run revision at the clone `DATABASE_URL`.
4. Time these clocks:

| Clock | Meaning | Measured |
|---|---|---|
| T_detect | operator notices primary is gone | — |
| T_restore | clone/PITR reachable | — |
| T_reconnect | app health `ok` on the clone URL | — |
| T_replay | Pub/Sub redelivery / outbox drain caught up | — |
| T_validate | ledger counts + a known `txn_id` match pre-fail notes | — |

5. Publish this table with timestamps. Until then, RPO/RTO stay TARGET.

## Related CI (not a game day)

- `test_queue_survives_worker_kill` — worker loss
- `test_notify_failure_does_not_break_ingest` — publish loss after DB commit
- `test_outbox_row_commits_with_queue` — outbox atomic with the queue
