# Corridor Watch — final validation report

<!-- FROZEN_EVIDENCE_PACK -->
All competition benchmark artifacts are frozen one-shot evaluations. Subsequent code changes are not used to alter or replace benchmark results.

Suite wrap run `5fcf08a2b0e3` commit `129bb69febcd` ts `2026-09-14T10:35:13.454904+00:00` — `reports/validation_report.json`. Seed `42`.
Each experiment below keeps its own run ID / commit / timestamp. Do not collapse them into one number.
Dictionary: `validation/METRICS.md`. Scoreboard: `reports/SCORECARD.md`. Provenance: `reports/BENCHMARK_PROVENANCE.md`.

## Benchmark A (generator A / hidden oracle)

run `5fcf08a2b0e3` commit `129bb69febcd` ts `2026-09-14T10:35:13.454904+00:00` — `reports/validation_report.json`

- n=586 F1=1.0 FPR=0.0
- Runtime ignores `fraud_scenario`. Gate F1 ≥ 0.85.

## Benchmark B (independent Dist B, frozen seed 7)

run `5ecbc68cafbd` commit `129bb69febcd` ts `2026-09-14T10:33:52.239511+00:00` — `reports/dist_b.json`
Before (same seed, pre-fix): precision=0.2593 F1=0.4118 FPR=1.0 (`reports/dist_b_before.json`).
After: precision=1.0 F1=1.0 FPR=0.0 TP=28 FP=0 FN=0 TN=80.

Hard-negative FPR is 0% on payroll/treasury/marketplace networks. Dist B "normal" is the same source-only star plus high corridor velocity. Before the inbound guard, velocity counted as split with no fan-in, so Dist B FPR was 100% while hard-negatives already stayed below flag.

| Hypothesis | Verdict |
|---|---|
| Temporal distribution shift | Ruled out (same clock family) |
| Transaction density | Contributing (burst outbound) but not sufficient |
| Account-age distribution | Ruled out (hub is old) |
| Velocity distribution | Yes, but only when scored as split without inbound |
| Graph topology | **Cause** — source-only star vs inbound mule/smurf |
| Beneficiary concentration | Ruled out |
| Shared devices | Ruled out |
| Legitimate organizational networks | Same topology as hard-neg payroll |
| Feature leakage | Ruled out (`fraud_scenario` eval-only) |
| Benchmark construction | Yes — generator B "normal" is a payroll star |

One model change: `split_vel = vel * 8` only if `fan_in >= 3` or `pass_through >= 0.3`. Frozen test remains seed 7; sweep used seed 11. Forensics: `reports/dist_b_false_positive_analysis.md`.

## Benchmark C (independent Dist C, frozen seed 23, one-shot)

run `5de896b7f460` commit `a4de7e1817a8` ts `2026-09-14T09:36:21.531397+00:00` — `reports/dist_c.json`

Freeze: `reports/dist_c_freeze.json`. Detector was not retuned on this seed. Threshold remains 40.

- n=102 precision=0.3333 recall=1.0 F1=0.5 FPR=0.7568
- Unseen fraud names: layering_cascade (middle hop dropped), dormant_wake, funnel_exit, mirror_peel. Not data_gen / Dist B labels.
- Normals: bipartite market, remittance mesh, FX hedge, JPY payroll, noise, ambiguous tuition/charity inbound.
- Do not treat a later retune against seed 23 as generalization.

Fan-in without pass-through, youth, short hold, or burst velocity is collection (tuition/charity/merchant), not a mule. That rule was fitted on Dist B + hard-neg + a seed-31 probe, **not** on frozen C.

## Benchmark D (independent Dist D, frozen seed 37, one-shot)

run `1d405ffd71a5` commit `8323b0486fc1` ts `2026-09-14T09:49:26.773725+00:00` — `reports/dist_d.json`

Freeze: `reports/dist_d_freeze.json`. Gate: recall ≥ 0.90, precision ≥ 0.80, FPR ≤ 0.10. Do not retune on seed 37.

- n=80 precision=0.587 recall=1.0 F1=0.7397 FPR=0.3585
- Unseen fraud: invoice_loop, nested_shell, drain_wake, burst_sink.
- Normals: tripartite farm-mill-shop, dividends, CHF trade, noise, ambiguous clinic/tithe.
- Clinic/tithe inbound: 0 flagged (collecting guard). Gate missed on precision/FPR: 19/36 `normal` flagged — mill pass-through (farm→mill→shop) has `ptr>=0.3`, so fan-in still counts. Detector was not retuned on D.

Pass-through on old book is commerce, not a mule. `collecting` requires `ptr>=0.3` **and** age≤90 (or youth/short-hold/burst). Graph hop depth on an old mesh is supply-chain, so hop/ptr mule terms also follow `collecting`. Fitted on Dist B + hard-neg + generator A + a seed-43 mill probe, **not** on frozen D.

## Benchmark E (independent Dist E, frozen seed 41, one-shot)

run `2e5062e5cf70` commit `0a0c06ce73ce` ts `2026-09-14T10:13:05.638392+00:00` — `reports/dist_e.json`

Freeze: `reports/dist_e_freeze.json`. Gate: recall ≥ 0.90, precision ≥ 0.80, FPR ≤ 0.10. Do not retune on seed 41.

- n=84 precision=1.0 recall=1.0 F1=1.0 FPR=0.0
- Unseen fraud: round_trip_peel, skip_hop, dormant_drain, pulse_smurf.
- Normals: four-stage mine-smelter-trader-yard, royalties, MXN trade, noise, ambiguous levy/dues.
- Levy/dues inbound and commercial pass-through: 0 flagged.

## Benchmark F (independent Dist F, frozen seed 47, one-shot)

run `4eb8ce459421` commit `129bb69febcd` ts `2026-09-14T10:31:36.867404+00:00` — `reports/dist_f.json`

Freeze: `reports/dist_f_freeze.json`. Gate: recall ≥ 0.90, precision ≥ 0.85, FPR ≤ 0.10, taxonomy_accuracy > 0. Do not retune on seed 47.

`business_context` names commerce vs burst vs mule vs collection from graph features already on the score row. `pick_primary` names split on inbound burst and multi_hop on collecting layering; detection scores stay argmax. Fitted on Dist B + hard-neg + A + probe 43, **not** on frozen F. Deterministic verdict uses the higher-risk account's stored primary (does not re-argmax merged pattern_scores).

- n=81 precision=1.0 recall=1.0 F1=1.0 FPR=0.0
- Exact pattern_accuracy=0.0 (novel names vs five DNA labels).
- taxonomy_accuracy=0.25 mapping_coverage=0.75 novel_detection_recall=1.0
- Mapped: dock_smurf→split, berth_skip→multi_hop, quay_wake→mule. Unmapped novel: trade_overbill.
- `pattern_accuracy` is exact canonical Pattern DNA label agreement (structurally 0 on novel generator names).
- `taxonomy_accuracy` uses an eval-only FAMILY map declared in `generator_f.py` **before** the run. Runtime never sees those names and does not add Dist F labels to Pattern DNA.
- Unmapped families stay novel (`novel_detection_recall`) rather than being renamed to a DNA string.
- FAMILY is eval-only. Runtime ignores fraud_scenario.

## Hard negatives

run `49dc0b84dff6` commit `129bb69febcd` ts `2026-09-14T10:33:55.354421+00:00` — `reports/hard_negative_results.json`

- n=71 FPR=0.0 precision=1.0 recall=1.0
- 10 legit archetypes + fraud twins. Not 7 isolated wires.

## Network v2 (investigation-useful)

Full-graph account recall run `5fcf08a2b0e3` commit `129bb69febcd` ts `2026-09-14T10:35:13.454904+00:00` — `reports/network_metrics.json`: account=1.0
v2 run `f2d4819f442a` commit `129bb69febcd` ts `2026-09-14T10:33:55.575017+00:00` — `reports/network_evaluation_v2.json`: anchor=0.8333 critical-node=1.0 critical-edge=1.0 path=0.6667 recall@10=1.0

Old full-graph line and v2 are different metrics. Do not substitute.

## Gemini

### Absolute 5-model comparison (canonical)

**Dist G — GenAI unknown** (`reports/genai_dist_g_bakeoff.md`, freeze `reports/dist_g_freeze.json`, run_id `982d59f1f0e4`): seed 53, n=80 (32 fraud / 48 benign). Novel families disjoint from Dist A–F. All five models **P=1.0 R=0.4688 F1=0.6383 FPR=0.0**. Selected **`gemini-2.5-flash` at $0.002012/case** (agr=1.0, p95=6720ms). Recall is honest: GenAI tracks the DAG and does not recover novel `tarmac_drip` detector misses.

| Model | P | R | F1 | FPR | $/case | p95 ms |
|---|---:|---:|---:|---:|---:|---:|
| `gemini-2.5-flash` ★ | 1.0 | 0.4688 | 0.6383 | 0.0 | **0.002012** | 6720 |
| `gemini-3.8-flash` | 1.0 | 0.4688 | 0.6383 | 0.0 | 0.003233 | 73814 |
| `gemini-3.6-flash` | 1.0 | 0.4688 | 0.6383 | 0.0 | 0.004128 | 7911 |
| `gemini-2.5-pro` | 1.0 | 0.4688 | 0.6383 | 0.0 | 0.010252 | 10153 |
| `gemini-3.1-pro-preview` | 1.0 | 0.4688 | 0.6383 | 0.0 | 0.018887 | 16499 |

**Agreement + USD** (`reports/genai_agreement_cost_bakeoff.md`, run_id `18c9176f68de`): golden n=100 × 5 models. Selected **`gemini-2.5-flash` at $0.002032/case** (agr=1.0).

| Model | Agreement | $/case | p95 ms | Alert FPR |
|---|---:|---:|---:|---:|
| `gemini-2.5-flash` ★ | 1.0 | **0.002032** | 6654 | 0.0 |
| `gemini-3.8-flash` | 1.0 | 0.003405 | 15377 | 0.0 |
| `gemini-3.6-flash` | 1.0 | 0.004045 | 10029 | 0.0 |
| `gemini-2.5-pro` | 0.99 | 0.010631 | 10377 | 0.022 |
| `gemini-3.1-pro-preview` | 1.0 | 0.018758 | 16218 | 0.0 |

Methodology: [`docs/GENAI_MODEL_BENCHMARK.md`](docs/GENAI_MODEL_BENCHMARK.md).

### Historical single-model baseline

run `unstamped` commit `not-recorded` ts `not-recorded` — `reports/gemini_agreement.json`

- agreement=1.0 schema_valid=100 invoked=100 CI=[0.963, 1.0]
- p95=4025.4 ms (gate 8000) model=gemini-2.5-flash cost/case=0.00143 tokens/case=1397.3
- Hallucination run `unstamped` commit `not-recorded` ts `not-recorded` — `reports/hallucination.json`: gate=0.0 unsupported=0.0 entity=0.0 numerical=0.0 live ungrounded=0.0 n=100 (live model hallucination rate NOT_MEASURED)

If this artifact has no `git_commit`, it was measured before experiment stamping. Numbers are still the live n=100 run; do not backfill a commit. This pack is **not** the 5-model comparison (see Dist G / agreement+USD above).

## DeepEval

run `147e429d8a39` commit `7d22cff27eaa` ts `2026-09-14T09:16:26.450799+00:00` — `reports/deepeval.json`

- `ran`=True n=205 official=RAN faithfulness=1.0 official_n=10
- Empty runner stays `ran: false` n=1. This row is Verified only at n≥100 real investigation reports.

| kind | n |
|---|---|
| adversarial | 5 |
| contradict | 15 |
| document | 20 |
| hardneg | 15 |
| hop | 20 |
| hybrid | 10 |
| injection | 20 |
| missing | 15 |
| mule | 20 |
| normal | 20 |
| partial | 10 |
| subtle | 20 |
| toolfail | 15 |

| metric | mean |
|---|---|
| EvidenceGroundingMetric | 1.0 |
| UnsupportedClaimsMetric | 1.0 |
| AmlCorrectnessMetric | 1.0 |
| EvidenceCompletenessMetric | 1.0 |
| VerdictStabilityMetric | 1.0 |

Mix: normal, obvious fraud (mule/hop), subtle fraud, hard negatives, partial visibility, contradictory evidence, missing evidence, document cases, prompt injection, tool failure, hybrid/novel.

## Scale

run `unstamped` commit `not-recorded` ts `not-recorded` — `reports/scale/live_gates.json`

| Target | Publish TPS | Consume TPS | Gate | Result |
|---|---:|---:|---|---|
| 100 | 99.97 | 97.59 | 95 | passed |
| 500 | 499.75 | 407.96 | 400 | passed |
| 1,000 | 999.5 | 814.13 | 800 | passed |
| 2,000 | 1999.64 | 1148.32 | 1500 | missed |

Max sustained ingest under a passing gate: **814.13**. 5,000 TPS remains Target.

## Investigation throughput

Enqueue-only run `unstamped` commit `not-recorded` ts `not-recorded` — `reports/scale/investigation_throughput.json`: enqueue_tps=119.77
Completion run `unstamped` commit `not-recorded` ts `not-recorded` — `reports/investigation_throughput_v2.json`: Policy A 74.76/sec p95=16.0 ms. Policy B Gemini 0.36/sec p95=4633.9 ms n=10.

Enqueue ≠ completion. Neither is ingest TPS.

## Security

run `unstamped` commit `not-recorded` ts `not-recorded` — `reports/injection_decision.json` decision-change=0.0 n=50
RBAC / PII / Gemini-off-ingest: Verified tests under `validation/security/` and `validation/reliability/`.
Concurrent races run `unstamped` commit `not-recorded` ts `not-recorded` — `reports/races.json`: failures=0
Rule-miner holdout run `unstamped` commit `not-recorded` ts `not-recorded` — `reports/rule_miner_holdout.json`: precision=1.0

## DR

run `unstamped` commit `not-recorded` ts `not-recorded` — `reports/dr_gameday.json`

- RTO=4.5 min. Clone RPO=0.0 min (current-state). PITR-to-past NOT_MEASURED.

## Known limitations

- Synthetic ledgers only. No production bank integration.
- **814 TPS** measured sustained ingest under the defined SLO. **5,000 TPS is a target, not achieved.** 2,000 TPS consume missed the 1500 gate (measured 1148). SQL-bound.
- Dist C FPR 0.7568 / F1 0.5 and Dist D FPR 0.3585 / F1 0.7397 are frozen false-positive misses. Detector was not retuned on C or D.
- Full investigation-path recall = **0.667** (not 1.0).
- Exact novel taxonomy classification remains imperfect: Dist F `pattern_accuracy` 0.0, `taxonomy_accuracy` 0.25. Unmapped `trade_overbill` was detected (recall 1.0) without being assigned a DNA name.
- Dist B exact name-match is 0 (generator names ≠ DNA labels). Confusion: `burst_smurf` → `split_transaction_laundering`, `circular_pass` → `multi_hop_chain`. Detection F1 is the scored metric.
- Official Gemini Faithfulness evaluation is **n=10**, not the 205-case DeepEval mix.
- PITR-to-past RPO is NOT_MEASURED. Clone RPO 0.0 min is current-state only.
- Policy B Gemini completion is 0.36 TPS on n=10. Not a fleet number.
- Dist E/F: 100% recall on those frozen unseen fraud families is not 100% accuracy on all fraud.
