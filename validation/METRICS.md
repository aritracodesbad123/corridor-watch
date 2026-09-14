# Validation metric dictionary

Every SCORECARD row maps here. Do not upgrade a claim without the named artifact.

| Name | Formula | Unit | n | Gate | Artifact | Kind | Statistically meaningful | Limitations |
|---|---|---|---|---|---|---|---|---|
| Detector F1 | 2PR/(P+R) on risk≥40 vs hidden oracle | 0–1 | clean-cut rows | ≥0.85 | `reports/validation_report.json` | deterministic | yes on that cut | Generator A; labels eval-only |
| Detector FPR | FP/(FP+TN) | 0–1 | same | ≤0.10 | same | deterministic | yes | same |
| Dist B F1 | same on generator B (frozen seed 7) | 0–1 | Dist B rows | recorded | `reports/dist_b.json` (baseline `dist_b_before.json`) | deterministic | small n | Not AMLSim; do not tune on seed 7 |
| Dist C F1 | same on generator C (frozen seed 23, one-shot, pinned) | 0–1 | Dist C rows | recorded | `reports/dist_c.json` (freeze `dist_c_freeze.json`) | deterministic | small n | Do not retune on seed 23; do not overwrite |
| Dist D F1 | same on generator D (frozen seed 37, one-shot, pinned) | 0–1 | Dist D rows | recall≥0.90 precision≥0.80 FPR≤0.10 (missed; measured F1 0.7397) | `reports/dist_d.json` (freeze `dist_d_freeze.json`) | deterministic | small n | Mill pass-through FPs; do not retune on seed 37; do not overwrite |
| Dist E F1 | same on generator E (frozen seed 41, one-shot, pinned) | 0–1 | Dist E rows | recall≥0.90 precision≥0.80 FPR≤0.10 | `reports/dist_e.json` (freeze `dist_e_freeze.json`) | deterministic | small n | Do not retune on seed 41; do not overwrite |
| Dist F F1 | detection F1 on generator F (frozen seed 47, one-shot) | 0–1 | Dist F rows | recall≥0.90 precision≥0.85 FPR≤0.10 and taxonomy>0 | `reports/dist_f.json` (freeze `dist_f_freeze.json`) | deterministic | small n | Last freeze; do not retune on seed 47 |
| Dist F taxonomy | mapped positives where primary == FAMILY[scenario] | 0–1 | mapped Dist F positives | >0 | `reports/dist_f.json` | eval-only map | small n | `pattern_accuracy` is exact DNA-name match. `taxonomy_accuracy` is the pre-declared FAMILY map only. Unmapped families stay novel (`novel_detection_recall`). Runtime never reads `fraud_scenario` and Dist F names are not Pattern DNA labels |
| Network account recall | \|pred∩truth\|/\|truth\| nodes per connected component | 0–1 | flagged networks | recorded | `reports/network_metrics.json` | deterministic | medium | Component = one investigation, not every mule in the ledger |
| Network v2 anchor/critical/path/recall@K | investigation-useful subset | 0–1 | Dist B + hard-neg clusters | recorded | `reports/network_evaluation_v2.json` | deterministic | medium | Does not replace account recall |
| Gemini agreement | agree/n vs deterministic disposition | 0–1 | `agreement_n` | ≥0.85 | `reports/gemini_agreement.json` | LLM | only if n≥100 | n=3 is not 100% |
| Gemini p95 | 95th percentile latency | ms | invoked_n | ≤8000 | same | measured | only if n≥100 | 3-sample p95 is brittle |
| Gemini cost/case | mean USD from usage_metadata | USD | scored | ≤0.05 | same | measured | small n | model/price table |
| Gemini tokens/case | mean prompt+completion | tokens | scored | none | same | measured | small n | |
| Hallucination rate | invented material that survived the grounding gate | 0–1 | trap+live n | ≤0.05 | `reports/hallucination.json` | mixed | trap suite is constructed | Split from unsupported/entity/numerical |
| Unsupported claim rate | unsupported_ids / claim_ids after gate | 0–1 | same | ≤0.05 | same | deterministic gate | yes for gate | Pre-gate rate is `unsupported_claim_rate_pre_gate` |
| Entity error rate | invented entity tokens that survived the gate | 0–1 | trap | =0 | same | deterministic gate | trap | |
| Numerical error rate | invented numbers that survived the gate | 0–1 | trap | =0 | same | deterministic gate | trap | |
| Injection decision-change | flipped HOLD/ESCALATE/FREEZE / attacks | 0–1 | corpus ≥50 | =0 | `reports/injection_decision.json` | mixed | corpus still synthetic | Redaction ≠ this metric |
| Ingest TPS | processed / (publish+drain) | TPS | live probe | gates 95/400/800/1500 | `reports/scale/test_*_tps.json` | measured | 10–20s probes | Not 5,000 TPS |
| Investigation enqueue TPS | queued_for_investigation / elapsed | TPS | same probes | recorded | `reports/scale/investigation_throughput.json` | measured | enqueue ≠ completion | Not ingest TPS |
| Investigation completion TPS | investigations finished / drain time | TPS | local backlog | recorded | `reports/investigation_throughput_v2.json` | measured | Policy A deterministic; Policy B only if live Gemini | Not 5,000 TPS |
| Hard-negative FPR | flagged legit network txns / legit n | 0–1 | 10 archetypes + twins | ≤0.10 | `reports/hard_negative_results.json` | deterministic | still synthetic | Not 7 isolated wires |
| Hybrid detection rate | flagged / hybrid n | 0–1 | hybrid set | recorded | `reports/hybrid.json` | deterministic | small | Unseen combos |
| Rule-miner holdout precision | TP/(TP+FP) on 30% holdout | 0–1 | decisions | recorded | `reports/rule_miner_holdout.json` | deterministic | needs decisions | Defaults are NOT_MEASURED |
| RTO | clone RUNNABLE − start | min | 1 game day | recorded | `reports/dr_gameday.json` | measured | n=1 | Current-state clone |
| PITR-to-past RPO | restore gap | min | — | — | same | NOT_MEASURED | no | Do not treat clone RPO as PITR |
| Replay duplicates | count after replay | count | — | — | same | NOT_MEASURED | no | Hardcoded 0 retired |
| DeepEval BaseMetric n | cases scored / ran flag | count | ≥100 mixed kinds | ran:true | `reports/deepeval.json` | deterministic wrappers | yes at n≥100 | Official FaithfulnessMetric separate; empty runner is ran:false n=1 |
| Official Gemini Faithfulness | Gemini-as-judge FaithfulnessMetric | 0–1 | **10** | recorded | `reports/deepeval.json` | LLM judge | small n | Not the 205-case mix |
| 5,000 TPS | — | TPS | — | TARGET | none | TARGET | no | Never claim achieved |

All competition benchmark artifacts are frozen one-shot evaluations. Subsequent code changes are not used to alter or replace benchmark results. Provenance: `reports/BENCHMARK_PROVENANCE.md`.

## Dist F taxonomy (eval-only)

`pattern_accuracy` measures exact canonical Pattern DNA label agreement. Generator F names (`dock_smurf`, `berth_skip`, `quay_wake`, `trade_overbill`) are disjoint from the five runtime DNA labels, so exact match is expected to be 0. Those names were **not** added to Pattern DNA or to Gemini `VerdictSchema`.

`taxonomy_accuracy` uses an explicitly documented evaluation-only semantic family mapping declared in `validation/external/generator_f.py` (`FAMILY`) **before** the frozen run:

- `dock_smurf` → `split_transaction_laundering`
- `berth_skip` → `multi_hop_chain`
- `quay_wake` → `mule_pass_through`
- `trade_overbill` — **unmapped novel**. Not renamed to a DNA string.

Among mapped positives, `taxonomy_accuracy` is the fraction where `primary_pattern == FAMILY[scenario]`. `mapping_coverage` is mapped positives / all positives. `novel_detection_recall` is the fraction of unmapped positives that were flagged (detection without claiming a DNA name). Runtime ignores `fraud_scenario`.

