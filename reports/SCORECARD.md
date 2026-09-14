# Corridor Watch — validation scorecard

Seed `42`. Do not upgrade a row without a new artifact.

| Claim | Status | Evidence |
|---|---|---|
| Detector F1 | Verified 1.0 | `validation/deterministic/test_detection.py` / clean `data_gen` cut |
| Gemini grounding | Verified | `validation/deepeval/test_grounding.py` |
| Gemini vs deterministic agreement | Verified **1.0** (gate 0.85) | `reports/gemini_agreement.json` |
| Hallucination rate / cost per case | Verified $0.002229 (gate $0.05) | `reports/gemini_agreement.json` |
| Gemini p95 | Verified 7754.5 ms (gate 8000) | `reports/gemini_agreement.json` |
| 100 TPS consume | Verified **97.59** (gate 95) | `reports/scale/test_100_tps.json` |
| 500 TPS consume | Verified **407.96** (gate 400) | `reports/scale/test_500_tps.json` |
| 1,000 TPS consume | Verified **814.13** (gate 800) | `reports/scale/test_1000_tps.json` |
| 2,000 TPS consume | Missed **1148.32** (gate 1500) | `reports/scale/test_2000_tps.json` |
| Max sustained TPS under SLO | Measured 814.13 | passing 1k gate; 2k miss |
| RTO/RPO | Measured RPO 0.0 min / RTO 4.5 min | `reports/dr_gameday.json` |
| 5,000 TPS | Target | not claimed as achieved |
| Idempotent ingest | Verified | `validation/reliability/test_idempotency.py` |
| Queue recovery | Verified | `validation/reliability/test_queue_recovery.py` |
| Gemini off ingest | Verified | `validation/reliability/test_gemini_isolation.py` |
| RBAC high-risk | Verified | `validation/security/test_rbac.py` |
| PII tokens at Gemini boundary | Verified | `validation/security/test_pii_minimization.py` |

Suite root is `validation/` (not `evaluation/`) because `evaluation.py` already exists.
DeepEval folder name only — metrics are pytest/stdlib.
