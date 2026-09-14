# Corridor Watch — validation scorecard

run_id `92ec5a8bd4c3` commit `8beb0b0deed4938e87516e931ea79ee35a91b524`. Seed `42`.
Do not upgrade a row without a new artifact. Dictionary: `validation/METRICS.md`.

| Claim | Status | Evidence |
|---|---|---|
| Detector F1 | Verified 1.0 | `validation/deterministic/test_detection.py` / hidden oracle |
| Dist B F1 | Verified 0.4118 | `reports/dist_b.json` |
| Network account recall | Verified 0.2019 | `reports/network_metrics.json` |
| Gemini grounding | Verified | `validation/deepeval/test_grounding.py` |
| Gemini vs deterministic agreement | Verified **1.0** n=3 CI=[0.4385, 1.0] (gate 0.85) | `reports/gemini_agreement.json` |
| Hallucination rate | Verified 0.0 (live n=3; trap/gate — not 0% on 100 live cases) | `reports/hallucination.json` |
| Unsupported claim rate | Verified 0.5 | `reports/hallucination.json` |
| Gemini cost per case | Verified $ 0.002229 | `reports/gemini_agreement.json` |
| Gemini tokens per case | Verified 1845.7 | `reports/gemini_agreement.json` |
| Gemini p95 | Verified 7754.5 ms (gate 8000) | `reports/gemini_agreement.json` |
| Injection decision-change | Verified 0.0 | `reports/injection_decision.json` |
| DeepEval package | Verified import + custom BaseMetric | `reports/deepeval.json` |
| 100 TPS consume | Verified **97.59** (gate 95) | `reports/scale/test_100_tps.json` |
| 500 TPS consume | Verified **407.96** (gate 400) | `reports/scale/test_500_tps.json` |
| 1,000 TPS consume | Verified **814.13** (gate 800) | `reports/scale/test_1000_tps.json` |
| 2,000 TPS consume | Missed **1148.32** (gate 1500) | `reports/scale/test_2000_tps.json` |
| Max sustained ingest TPS under SLO | Measured 814.13 | passing 1k gate; 2k miss |
| Investigation enqueue TPS | Verified 119.77 | `reports/scale/investigation_throughput.json` |
| Hard-negative FPR | Verified 0.0 | `reports/hard_negatives.json` |
| Concurrent race failures | Verified 0 | `reports/races.json` |
| Rule-miner holdout precision | NOT_MEASURED | `reports/rule_miner_holdout.json` |
| RTO/RPO | Measured RTO 4.5 min; clone RPO 0.0 min (current-state). PITR-to-past NOT_MEASURED | `reports/dr_gameday.json` |
| 5,000 TPS | Target | not claimed as achieved |
| Idempotent ingest | Verified | `validation/reliability/test_idempotency.py` |
| Queue recovery | Verified | `validation/reliability/test_queue_recovery.py` |
| Gemini off ingest | Verified | `validation/reliability/test_gemini_isolation.py` |
| RBAC high-risk | Verified | `validation/security/test_rbac.py` |
| PII tokens at Gemini boundary | Verified | `validation/security/test_pii_minimization.py` |

Suite root is `validation/` (not `evaluation/`) because `evaluation.py` already exists.
DeepEval is the real package plus custom BaseMetric wrappers. Official FaithfulnessMetric is NOT_MEASURED unless a Gemini judge binds.
