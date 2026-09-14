# Corridor Watch — validation scorecard

run_id `cedb4b314656` commit `7d22cff27eaa6d6074d46de6f1bd8ab879ffd3a0`. Seed `42`.
Do not upgrade a row without a new artifact. Dictionary: `validation/METRICS.md`.

| Claim | Status | Evidence |
|---|---|---|
| Detector F1 | Verified 1.0 | `validation/deterministic/test_detection.py` / hidden oracle |
| Dist B F1 | Verified 1.0 (before 0.4118, FPR 1.0) | `reports/dist_b.json` vs `reports/dist_b_before.json` |
| Network account recall | Verified 1.0 | `reports/network_metrics.json` |
| Network v2 anchor recall | Verified 0.8333 | `reports/network_evaluation_v2.json` |
| Network v2 critical-node recall | Verified 1.0 | `reports/network_evaluation_v2.json` |
| Network v2 investigation-path | Verified 0.6667 | `reports/network_evaluation_v2.json` |
| Network v2 recall@10 | Verified 1.0 | `reports/network_evaluation_v2.json` |
| Gemini grounding | Verified | `validation/deepeval/test_grounding.py` |
| Gemini vs deterministic agreement | Verified **1.0** schema_valid n=100 / invoked 100 CI=[0.963, 1.0] (gate 0.85) | `reports/gemini_agreement.json` |
| Hallucination rate | Verified trap/gate 0.0; live ungrounded 0.0 n=100 (live model rate NOT_MEASURED) | `reports/hallucination.json` |
| Unsupported claim rate | Verified 0.0 | `reports/hallucination.json` |
| Entity error rate | Verified 0.0 | `reports/hallucination.json` |
| Numerical error rate | Verified 0.0 | `reports/hallucination.json` |
| Gemini cost per case | Verified $ 0.00143 | `reports/gemini_agreement.json` |
| Gemini tokens per case | Verified 1397.3 | `reports/gemini_agreement.json` |
| Gemini p95 | Verified 4025.4 ms (gate 8000) | `reports/gemini_agreement.json` |
| Injection decision-change | Verified 0.0 | `reports/injection_decision.json` |
| DeepEval package | Verified n=205 kinds=13 BaseMetric (official RAN) | `reports/deepeval.json` |
| 100 TPS consume | Verified **97.59** (gate 95) | `reports/scale/test_100_tps.json` |
| 500 TPS consume | Verified **407.96** (gate 400) | `reports/scale/test_500_tps.json` |
| 1,000 TPS consume | Verified **814.13** (gate 800) | `reports/scale/test_1000_tps.json` |
| 2,000 TPS consume | Missed **1148.32** (gate 1500) | `reports/scale/test_2000_tps.json` |
| Max sustained ingest TPS under SLO | Measured 814.13 | passing 1k gate; 2k miss |
| Investigation enqueue TPS | Verified 119.77 | `reports/scale/investigation_throughput.json` |
| Investigation completion TPS (Policy A) | Verified 74.76 | `reports/investigation_throughput_v2.json` |
| Investigation time-to-verdict p95 (Policy A) | Verified 16.0 | `reports/investigation_throughput_v2.json` |
| Investigation Gemini TPS (Policy B) | Verified 0.36 | `reports/investigation_throughput_v2.json` |
| Hard-negative FPR | Verified 0.0 | `reports/hard_negative_results.json` |
| Concurrent race failures | Verified 0 | `reports/races.json` |
| Rule-miner holdout precision | Verified 1.0 | `reports/rule_miner_holdout.json` |
| RTO/RPO | Measured RTO 4.5 min; clone RPO 0.0 min (current-state). PITR-to-past NOT_MEASURED | `reports/dr_gameday.json` |
| 5,000 TPS | Target | not claimed as achieved |
| Idempotent ingest | Verified | `validation/reliability/test_idempotency.py` |
| Queue recovery | Verified | `validation/reliability/test_queue_recovery.py` |
| Gemini off ingest | Verified | `validation/reliability/test_gemini_isolation.py` |
| RBAC high-risk | Verified | `validation/security/test_rbac.py` |
| PII tokens at Gemini boundary | Verified | `validation/security/test_pii_minimization.py` |

Suite root is `validation/` (not `evaluation/`) because `evaluation.py` already exists.
DeepEval is Verified only when `reports/deepeval.json` has `ran: true` on ≥100 mixed investigation reports. Canonical narrative: `FINAL_VALIDATION_REPORT.md`. Official FaithfulnessMetric stays NOT_MEASURED unless a Gemini judge actually ran.
