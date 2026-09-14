# Corridor Watch — competition claims policy

Use this file during the presentation. Do not upgrade a status without a measured artifact.

Statuses:

- **Verified** — measured and reproducible from this repository.
- **Implemented** — built and functionally tested; not independently benchmarked at production scale.
- **Target** — desired capacity or future capability. Never present as achieved.

## Claims

| Claim | Status | Evidence |
|---|---|---|
| 5,000 TPS end-to-end ingest | **TARGET** | Synthetic goal. Do not display “5,000 TPS achieved.” |
| Pub/Sub → Cloud Run push ingest | **IMPLEMENTED** + tested | `/api/pubsub/push`, `pubsub_load_generator.py --pubsub` |
| Cloud SQL PostgreSQL persistence | **IMPLEMENTED** + benchmarked | `DATABASE_URL`; GCP refuses SQLite |
| Idempotent ingest | **VERIFIED** | `ON CONFLICT DO NOTHING` / `INSERT OR IGNORE`; `tests/test_platform.py` |
| Gemini off the ingest path | **VERIFIED** | `ingest_transaction` never calls Gemini |
| Deterministic investigation without Gemini | **IMPLEMENTED** | DAG + grounded report; Gemini optional |
| Investigation queue retry | **IMPLEMENTED** | `QUEUED → CLAIMED → RUNNING → COMPLETED / RETRY / DEAD_LETTER` |
| Transaction-only baseline vs Corridor Watch | **IMPLEMENTED** | `evaluation.compare_to_transaction_baseline` |
| Investigation compression | **IMPLEMENTED** | `graph.corridor.investigation_compression` |
| Pattern DNA match explainability | **IMPLEMENTED** | match strength, matched/missing signals |
| Evidence-addressable Gemini output | **IMPLEMENTED** | `InvestigationReport` IDs resolve to case evidence |
| High-risk freeze/hold/escalate | **VERIFIED** | Analyst receives `403 FIU Lead authorization required` |
| Production bank integration | **OUT OF SCOPE** | Synthetic world only |

## Measured ingest (do not invent numbers)

Published labels: [reports/SCORECARD.md](../reports/SCORECARD.md). Evidence pack (Sprint 4): [load-test](../production/load-test-report.md), [DR](../production/disaster-recovery-report.md), [threat model](../production/security-threat-model.md), [AI validation](../production/ai-model-validation-report.md).

Latest recorded Pub/Sub → Cloud Run → Cloud SQL results live in `GET /api/command-center` (`scorecard.ingest`), `production/load-test-report.md`, and `benchmarks/results/`.

Canonical command:

```bash
python pubsub_load_generator.py --pubsub --pretty --persist \
  --project YOUR_PROJECT --rate 5000 --duration 60 \
  --command-url https://YOUR_SERVICE --token FIU_BEARER
```

Report only `achieved_tps`. Publisher TPS is not consume TPS. `--in-process` ≠ HTTP ≠ Pub/Sub.

## Pool matrix (do not scale everything at once)

Measure one axis at a time before adding Cloud Run replicas:

| Cloud Run | Concurrency | Pool | Ingest slots |
|---:|---:|---:|---:|
| 2 | 8 | 4 | 4 |
| 2 | 16 | 8 | 8 |
| 5 | 8 | 4 | 4 |
| 5 | 16 | 8 | 8 |
| 10 | 16 | 8 | 8 |
| 10 | 32 | 8 | 8 |

Record achieved TPS, P50/P95/P99, 5xx rate, Pub/Sub backlog, instance count, and queue depth. Choose the winner from measurements.
