# Load-test report

**Status:** Measured on named paths. 5,000 TPS remains a **TARGET**.

Use this file in the presentation. Do not upgrade a row without a new artifact.

## Paths (do not mix them)

| Path | Command | What `achieved_tps` means |
|---|---|---|
| In-process | `pubsub_load_generator.py --in-process` | Local process only |
| HTTP batch | generator without `--pubsub` against `/api/ingest/batch` | API accept, not Cloud Run consume |
| Pub/Sub → Cloud Run → PostgreSQL | `--pubsub --command-url URL` | The honest scale path |

Publisher TPS is not consume TPS.

## Measured consume (Pub/Sub → Cloud Run → Cloud SQL)

Source: `docs/CLOUD_RUN.md`, 2026-09-13. SQL raised to `db-custom-2-7680`. Cloud Run max 10.

| SQL tier | Target | Published | Publish TPS | Ledger processed | Achieved TPS | P50 |
|---|---:|---:|---:|---:|---:|---:|
| db-f1-micro | 300 | 4,500 | 299.92 | 502 | **1.55** | 8.1s |
| db-custom-2-7680 | 200 | 4,000 | 199.95 | 2,402 | **5.65** | 118ms |

The publisher held the target. Consume stayed SQL/connector-bound (503s when the pool was cold or saturated).

**Maximum sustainable TPS under SLO on the live path: not established.** 5.65 TPS at a 200 target is a measurement, not a capacity claim.

## Local in-process (not Cloud Run)

Source: `benchmarks/latest.json` (`mode: in_process`, 2026-09-12).

| Field | Value |
|---|---|
| requested_rate | 5000 |
| duration_seconds | 1 |
| events_generated / accepted | 5000 / 5000 |
| achieved_tps | 1912.35 |
| queued_for_investigation | 546 |

Do not present 1,912 TPS as Cloud Run ingest.

## Plan matrix (still open)

The upgrade plan asked for 10–30 minute runs. Those cells are empty on purpose.

| Test | Rate | Duration | p95 | Errors | DB CPU | Notes |
|---|---:|---:|---:|---:|---:|---|
| Baseline | 100 TPS | 10m | — | — | — | not measured |
| Medium | 500 TPS | 30m | — | — | — | not measured |
| Heavy | 1K TPS | 30m | — | — | — | not measured |
| Stress | 2K TPS | 30m | — | — | — | not measured |
| Breakpoint | X | 10m | — | — | — | unknown until measured |

## How to add a row

```bash
python pubsub_load_generator.py --pubsub --pretty --persist \
  --project YOUR_PROJECT --rate 200 --duration 20 \
  --command-url https://YOUR_SERVICE --token FIU_BEARER
```

Record `achieved_tps`, P50/P95/P99, 5xx, Pub/Sub backlog, instance count, queue depth. Persist via `POST /api/benchmarks` as FIU lead. Do not invent DB CPU.

## Failure-mode checks already in CI

These are not load tests. They are the plan’s “does it behave when things go wrong” proofs:

| Failure | Test | Result |
|---|---|---|
| Duplicate Pub/Sub / source event | `test_ingest_is_idempotent`, `test_source_event_id_is_duplicate_across_message_ids` | one ledger row, one queue row |
| Notify/publish down after commit | `test_notify_failure_does_not_break_ingest` | queue row still exists |
| Investigation worker killed | `test_queue_survives_worker_kill` | `RETRY` then reclaim |
| Gemini unavailable | `test_gemini_unavailable_ingest_still_works` | ingest queued; deterministic report |
| GCP without Postgres | `test_gcp_refuses_sqlite` | process refuses SQLite |

See `docs/COMPETITION_CLAIMS.md`.
