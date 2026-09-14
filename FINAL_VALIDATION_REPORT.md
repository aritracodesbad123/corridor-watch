# Corridor Watch — final validation report

Suite wrap run `146d77ab27ef` commit `a4de7e1817a8` ts `2026-09-14T09:36:45.901166+00:00` — `reports/validation_report.json`. Seed `42`.
Each experiment below keeps its own run ID / commit / timestamp. Do not collapse them into one number.
Dictionary: `validation/METRICS.md`. Scoreboard: `reports/SCORECARD.md`.

## Benchmark A (generator A / hidden oracle)

run `146d77ab27ef` commit `a4de7e1817a8` ts `2026-09-14T09:36:45.901166+00:00` — `reports/validation_report.json`

- n=586 F1=1.0 FPR=0.0
- Runtime ignores `fraud_scenario`. Gate F1 ≥ 0.85.

## Benchmark B (independent Dist B, frozen seed 7)

run `df24a0df42aa` commit `7d22cff27eaa` ts `2026-09-14T09:16:27.072664+00:00` — `reports/dist_b.json`
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

## Hard negatives

run `c8045460f678` commit `7d22cff27eaa` ts `2026-09-14T09:16:27.154534+00:00` — `reports/hard_negative_results.json`

- n=71 FPR=0.0 precision=1.0 recall=1.0
- 10 legit archetypes + fraud twins. Not 7 isolated wires.

## Network v2 (investigation-useful)

Full-graph account recall run `146d77ab27ef` commit `a4de7e1817a8` ts `2026-09-14T09:36:45.901166+00:00` — `reports/network_metrics.json`: account=1.0
v2 run `9cd09cb73634` commit `7d22cff27eaa` ts `2026-09-14T09:16:27.371712+00:00` — `reports/network_evaluation_v2.json`: anchor=0.8333 critical-node=1.0 critical-edge=1.0 path=0.6667 recall@10=1.0

Old full-graph line and v2 are different metrics. Do not substitute.

## Gemini

run `unstamped` commit `not-recorded` ts `not-recorded` — `reports/gemini_agreement.json`

- agreement=1.0 schema_valid=100 invoked=100 CI=[0.963, 1.0]
- p95=4025.4 ms (gate 8000) model=gemini-2.5-flash cost/case=0.00143 tokens/case=1397.3
- Hallucination run `unstamped` commit `not-recorded` ts `not-recorded` — `reports/hallucination.json`: gate=0.0 unsupported=0.0 entity=0.0 numerical=0.0 live ungrounded=0.0 n=100 (live model hallucination rate NOT_MEASURED)

If this artifact has no `git_commit`, it was measured before experiment stamping. Numbers are still the live n=100 run; do not backfill a commit.

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

## Known failures

- 2,000 TPS consume missed the 1500 gate (measured 1148). SQL-bound. Not claimed as 5,000 TPS.
- Investigation-path recovery 0.6667 (not 1.0).
- Pattern accuracy on Dist B can be 0 even when F1 is 1.0 (`burst_smurf` → `mule_pass_through`). Detection F1 is the scored metric.
- Policy B Gemini completion is 0.36 TPS on n=10. Not a fleet number.
- PITR-to-past RPO is NOT_MEASURED.
- Dist C one-shot (seed 23): recall=1.0 FPR=0.7568 F1=0.5. High fan-in legit (tuition/charity/market) still flags. Detector was not retuned.
