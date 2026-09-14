# Corridor Watch — validation scorecard

<!-- FROZEN_EVIDENCE_PACK -->
All competition benchmark artifacts are frozen one-shot evaluations. Subsequent code changes are not used to alter or replace benchmark results.

Canonical wrap: `reports/validation_report.json` run `5fcf08a2b0e3`. Dictionary: `validation/METRICS.md`. Provenance: `reports/BENCHMARK_PROVENANCE.md`. Narrative: `FINAL_VALIDATION_REPORT.md`.

## Detection (Dist A–F)

| Claim | Status | Evidence |
|---|---|---|
| Dist A F1 | Verified 1.0 recall 1.0 FPR 0.0 (n=586, hidden oracle) | `reports/validation_report.json` / `validation/deterministic/test_detection.py` |
| Dist B F1 | Verified 1.0 recall 1.0 FPR 0.0 (seed 7; before F1 0.4118 FPR 1.0) | `reports/dist_b.json` vs `reports/dist_b_before.json` |
| Dist C F1 | Measured F1 0.5 recall 1.0 FPR 0.7568 (seed 23 one-shot, pinned) | `reports/dist_c.json` (freeze `reports/dist_c_freeze.json`) |
| Dist D F1 | Measured F1 0.7397 recall 1.0 FPR 0.3585 (seed 37 one-shot, pinned) | `reports/dist_d.json` (freeze `reports/dist_d_freeze.json`) |
| Dist E F1 | Verified F1 1.0 recall 1.0 FPR 0.0 (seed 41 one-shot) | `reports/dist_e.json` (freeze `reports/dist_e_freeze.json`) |
| Dist F detection | Verified F1 1.0 recall 1.0 precision 1.0 FPR 0.0 (seed 47 one-shot) | `reports/dist_f.json` (freeze `reports/dist_f_freeze.json`) |
| Dist F exact pattern_accuracy | Measured 0.0 (novel names ≠ five DNA labels) | `reports/dist_f.json` |
| Dist F taxonomy_accuracy | Measured 0.25 (eval-only FAMILY map; gate was >0) | `reports/dist_f.json` |
| Dist F mapping_coverage | Measured 0.75 | `reports/dist_f.json` |
| Dist F novel_detection_recall | Measured 1.0 (`trade_overbill` unmapped, still flagged) | `reports/dist_f.json` |
| Hard-negative FPR | Verified 0.0 (n=71) | `reports/hard_negative_results.json` |

100% recall on frozen unseen Dist E/F fraud families is not “100% accuracy on all fraud.” Dist C/D false-positive rates remain in the evidence pack.

## Network V2

| Claim | Status | Evidence |
|---|---|---|
| Network account recall | Verified 1.0 | `reports/network_metrics.json` |
| Network v2 anchor recall | Verified 1.0 on applicable clusters (1 cluster `not_applicable`, not a miss) | `reports/network_evaluation_v2.json` |
| Network v2 critical-node recall | Verified 1.0 | `reports/network_evaluation_v2.json` |
| Network v2 investigation-path | Verified 0.6667 | `reports/network_evaluation_v2.json` |
| Network v2 recall@10 | Verified 1.0 | `reports/network_evaluation_v2.json` |

## Gemini

| Claim | Status | Evidence |
|---|---|---|
| Gemini vs deterministic agreement | Verified **1.0**, n=100 invoked 100, CI=[0.963, 1.0] (gate 0.85) | `reports/gemini_agreement.json` |
| Gemini p95 | Verified **4.025 s** (4025.4 ms, gate 8000 ms) | `reports/gemini_agreement.json` |
| Gemini cost/case | Verified **$0.00143** | `reports/gemini_agreement.json` |
| Gemini tokens/case | Verified 1397.3 | `reports/gemini_agreement.json` |
| Gemini grounding | Verified | `validation/deepeval/test_grounding.py` |
| Hallucination rate | Verified trap/gate 0.0; live ungrounded 0.0 n=100 (live model rate NOT_MEASURED) | `reports/hallucination.json` |
| Unsupported / entity / numerical | Verified 0.0 after grounding gate | `reports/hallucination.json` |
| Injection decision-change | Verified 0.0 (n=50) | `reports/injection_decision.json` |

## DeepEval

| Claim | Status | Evidence |
|---|---|---|
| DeepEval package | Verified **205 cases**, 13 kinds, custom BaseMetric | `reports/deepeval.json` |
| Official Gemini Faithfulness | Verified **n=10**, score 1.0 (`FaithfulnessMetric/GeminiModel`) | `reports/deepeval.json` |

This is a 205-case DeepEval evaluation plus a 10-case official Gemini Faithfulness judge. It is not 205 Gemini-judged cases.

## Throughput

| Claim | Status | Evidence |
|---|---|---|
| 100 TPS consume | Verified **97.59** (gate 95) | `reports/scale/test_100_tps.json` |
| 500 TPS consume | Verified **407.96** (gate 400) | `reports/scale/test_500_tps.json` |
| 1,000 TPS consume | Verified **814.13** (gate 800) | `reports/scale/test_1000_tps.json` |
| 2,000 TPS consume | Missed **1148.32** (gate 1500) | `reports/scale/test_2000_tps.json` |
| Sustained ingest under SLO | Measured **814 TPS** (814.13; passing 1k gate, 2k miss) | `reports/scale/live_gates.json` |
| 5,000 TPS | **Target, not achieved** | not claimed as measured |

## Investigation throughput

| Claim | Status | Evidence |
|---|---|---|
| Investigation enqueue TPS | Verified 119.77 | `reports/scale/investigation_throughput.json` |
| Investigation completion TPS (Policy A) | Verified 74.76 | `reports/investigation_throughput_v2.json` |
| Investigation time-to-verdict p95 (Policy A) | Verified 16.0 ms | `reports/investigation_throughput_v2.json` |
| Investigation Gemini TPS (Policy B) | Verified 0.36 (n=10) | `reports/investigation_throughput_v2.json` |

Enqueue ≠ completion. Neither is ingest TPS.

## Security

| Claim | Status | Evidence |
|---|---|---|
| Idempotent ingest | Verified | `validation/reliability/test_idempotency.py` |
| Queue recovery | Verified | `validation/reliability/test_queue_recovery.py` |
| Gemini off ingest | Verified | `validation/reliability/test_gemini_isolation.py` |
| RBAC high-risk | Verified | `validation/security/test_rbac.py` |
| PII tokens at Gemini boundary | Verified | `validation/security/test_pii_minimization.py` |
| Concurrent race failures | Verified 0 | `reports/races.json` |
| Rule-miner holdout precision | Verified 1.0 | `reports/rule_miner_holdout.json` |

## DR

| Claim | Status | Evidence |
|---|---|---|
| RTO / clone RPO | Measured RTO 4.5 min; clone RPO 0.0 min (current-state) | `reports/dr_gameday.json` |
| PITR-to-past | NOT_MEASURED | `reports/dr_gameday.json` |

## Known limitations

- Synthetic ledgers only. No production bank integration.
- **814 TPS** measured sustained ingest under the defined SLO. **5,000 TPS is a target, not achieved.**
- Dist C FPR 0.7568 and Dist D FPR 0.3585 are frozen misses (commercial/mill pass-through false positives).
- Full investigation-path recall = **0.667**.
- Exact novel taxonomy classification remains imperfect (Dist F `pattern_accuracy` 0.0; `taxonomy_accuracy` 0.25).
- PITR-to-past RPO is NOT_MEASURED.
- Official Gemini Faithfulness evaluation is **n=10**, not n=205.
