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
| Hidden evaluation oracle (runtime ignores `fraud_scenario`) | **VERIFIED** | `validation/oracle/test_leakage.py` |
| Independent Dist B (not `data_gen`) | **VERIFIED** F1 1.0 / FPR 0.0 on frozen seed 7 (was F1 0.4118 / FPR 1.0) | `reports/dist_b.json` vs `reports/dist_b_before.json`. Threshold sweep used seed 11 only. |
| Independent Dist C (not A/B) | **MEASURED** one-shot seed 23: F1 0.5 / recall 1.0 / FPR 0.7568 (pinned) | `reports/dist_c.json`. Freeze `reports/dist_c_freeze.json`. Do not retune. Do not overwrite. |
| Independent Dist D (not A/B/C) | **MEASURED** one-shot seed 37: F1 0.7397 / recall 1.0 / precision 0.587 / FPR 0.3585 (missed precision≥0.80 FPR≤0.10, pinned) | `reports/dist_d.json`. Freeze `reports/dist_d_freeze.json`. Clinic/tithe 0 flagged; mill pass-through FPs. Do not retune. Do not overwrite. |
| Independent Dist E (not A/B/C/D) | **VERIFIED** one-shot seed 41: F1 1.0 / recall 1.0 / precision 1.0 / FPR 0.0 | `reports/dist_e.json`. Freeze `reports/dist_e_freeze.json`. Levy/dues and commercial pass-through 0 flagged. Do not retune. |
| Network account/key-node recall | **VERIFIED** 1.0 per connected component | `reports/network_metrics.json` (was ~0.17 when every mule in the ledger was one “truth” graph) |
| Network v2 investigation-useful | **IMPLEMENTED** | `reports/network_evaluation_v2.json` — anchor 0.83, critical-node 1.0, path 0.67, recall@10 1.0 |
| DeepEval package + custom metrics | **VERIFIED** n≥200 mixed investigation reports `ran: true` | `reports/deepeval.json`. Kinds include normal, obvious/subtle fraud, hardneg, partial, contradict, missing, document, injection, toolfail, hybrid. Official FaithfulnessMetric **RAN** n=10 score 1.0 (carry-forward if live judge not re-run). |
| Gemini agreement n≥100 | **VERIFIED** | `reports/gemini_agreement.json` invoked 100/100, schema_valid 100, agreement 1.0 CI 0.963–1.0. p95 **4025 ms** (gate 8000) on `gemini-2.5-flash`, prompt investigator-v9. |
| Hallucination / unsupported / entity / numerical | **VERIFIED** trap/gate (live hallucination **NOT_MEASURED** as a model rate) | `reports/hallucination.json` — post-gate unsupported 0.0; entity and numerical traps caught |
| Injection decision-change | **VERIFIED** 0.0 on n=50 | `reports/injection_decision.json` |
| Hard-negative network FPR | **VERIFIED** 0.0 (n=71, 10 legit archetypes + fraud twins) | `reports/hard_negative_results.json` |
| Investigation completion TPS | **MEASURED** Policy A 74.76 local (p95 16 ms); Policy B Gemini 0.36 TPS (p95 4634 ms, n=10) | `reports/investigation_throughput_v2.json`. Ingest ceiling remains **814.13** TPS. Not 5,000 TPS. |
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
