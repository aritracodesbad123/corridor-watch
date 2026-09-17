# Corridor Watch — competition claims policy

Use this file during the presentation. Do not upgrade a status without a measured artifact.
Canonical numbers: [`reports/SCORECARD.md`](../reports/SCORECARD.md). Judge brief: [`COMPETITION.md`](COMPETITION.md).

All competition benchmark artifacts are frozen one-shot evaluations. Subsequent code changes are not used to alter or replace benchmark results.

Statuses:

- **Verified** — measured and reproducible from this repository.
- **Implemented** — built and functionally tested; not independently benchmarked at production scale.
- **Target** — desired capacity or future capability. Never present as achieved.

## Claims

| Claim | Status | Evidence |
|---|---|---|
| 5,000 TPS end-to-end ingest | **TARGET** | Not achieved. Do not display “5,000 TPS platform.” |
| Sustained ingest under the defined SLO | **MEASURED 814 TPS** (814.13) | Passing 1,000 TPS gate (consume 814.13); 2,000 TPS gate missed (1148.32). `reports/scale/` |
| Pub/Sub → Cloud Run push ingest | **IMPLEMENTED** + tested | `/api/pubsub/push` |
| Cloud SQL PostgreSQL persistence | **IMPLEMENTED** + benchmarked | `DATABASE_URL`; GCP refuses SQLite |
| Idempotent ingest | **VERIFIED** | `ON CONFLICT DO NOTHING` / `INSERT OR IGNORE` |
| Gemini off the ingest path | **VERIFIED** | `ingest_transaction` never calls Gemini |
| Deterministic investigation without Gemini | **IMPLEMENTED** | DAG + grounded report; Gemini optional |
| Hidden evaluation oracle (runtime ignores `fraud_scenario`) | **VERIFIED** | `validation/oracle/test_leakage.py` |
| Dist A (generator A / hidden oracle) | **VERIFIED** F1 1.0 / recall 1.0 / FPR 0.0 n=586 | `reports/validation_report.json` |
| Independent Dist B | **VERIFIED** F1 1.0 / FPR 0.0 seed 7 (was F1 0.4118 / FPR 1.0) | `reports/dist_b.json` |
| Independent Dist C | **MEASURED** seed 23: F1 0.5 / recall 1.0 / FPR 0.7568 (pinned miss) | `reports/dist_c.json` |
| Independent Dist D | **MEASURED** seed 37: F1 0.7397 / recall 1.0 / FPR 0.3585 (pinned miss) | `reports/dist_d.json` |
| Independent Dist E | **VERIFIED** seed 41: F1 1.0 / recall 1.0 / FPR 0.0 | 100% recall on **that frozen unseen set**, not all fraud. `reports/dist_e.json` |
| Independent Dist F | **VERIFIED** seed 47: detection F1 1.0 / FPR 0.0; exact pattern_accuracy 0.0; taxonomy_accuracy 0.25 | Eval-only FAMILY map. Unmapped `trade_overbill` stays novel. `reports/dist_f.json` |
| Network v2 investigation-useful | **VERIFIED** critical-node 1.0, path 0.667, recall@10 1.0; anchor 1.0 on applicable clusters (1 cluster `not_applicable`) | `reports/network_evaluation_v2.json` |
| DeepEval | **VERIFIED 205 cases** custom BaseMetric | Plus a **10-case** official Gemini Faithfulness judge. Not 205 Gemini-judged cases. `reports/deepeval.json` |
| Gemini agreement | **VERIFIED 1.0, n=100** | Historical single-model pack `reports/gemini_agreement.json` |
| Gemini p95 | **VERIFIED 4.025 s** (4025.4 ms, gate 8000) | `gemini-2.5-flash` on that pack |
| Gemini cost/case | **VERIFIED $0.00143** (historical) / **$0.00201** Dist G flash | Absolute 5-model USD: Dist G + agreement bake-offs |
| Dist G GenAI unknown (5 models) | **VERIFIED** P 1.0 R 0.4688 F1 0.6383 FPR 0.0; USD winner **flash $0.002012** | `reports/genai_dist_g_bakeoff.md` |
| Agreement+USD (5 models) | **VERIFIED** flash agr 1.0 **$0.002032**/case | `reports/genai_agreement_cost_bakeoff.md` |
| Hallucination / unsupported / entity / numerical | **VERIFIED** trap/gate (live model hallucination rate **NOT_MEASURED**) | `reports/hallucination.json` |
| Injection decision-change | **VERIFIED** 0.0 on n=50 | `reports/injection_decision.json` |
| Hard-negative network FPR | **VERIFIED** 0.0 (n=71) | `reports/hard_negative_results.json` |
| Investigation completion TPS | **MEASURED** Policy A 74.76 local; Policy B Gemini 0.36 TPS n=10 | Not ingest TPS. Not 5,000 TPS. |
| High-risk freeze/hold/escalate | **VERIFIED** | Analyst receives `403 FIU Lead authorization required` |
| Production bank integration | **OUT OF SCOPE** | Synthetic world only |

## Dist F taxonomy (do not confuse with DNA accuracy)

`pattern_accuracy` measures exact canonical Pattern DNA label agreement.

`taxonomy_accuracy` uses an explicitly documented evaluation-only semantic family mapping declared in `validation/external/generator_f.py` before the frozen run.

Novel/unmapped families remain novel rather than being forcibly assigned to an existing Pattern DNA label. Dist F generator names were **not** added as runtime Pattern DNA labels.

## Measured ingest (do not invent numbers)

Publisher TPS is not consume TPS. `--in-process` ≠ HTTP ≠ Pub/Sub. Report only `achieved_tps`.
