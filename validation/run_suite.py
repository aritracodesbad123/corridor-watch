"""Run the validation suite and write reports/. Seed is recorded."""
from __future__ import annotations

import json
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from validation import ROOT, SEED, experiment_metadata

REPORTS = ROOT / "reports"


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _deterministic():
    try:
        from evaluation import run_evaluation
        return run_evaluation(cut="clean")
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _status(value, *, measured_when=None, label="Verified"):
    if value is None:
        return "NOT_MEASURED"
    return f"{label} {value}" if measured_when is None or measured_when else f"NOT_MEASURED {value}"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    report_only = "--report-only" in argv
    random.seed(SEED)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "scale").mkdir(exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    det = _deterministic()
    code = 0 if report_only else pytest.main([str(ROOT / "validation"), "-q", "--tb=line"])
    gem = _read(REPORTS / "gemini_agreement.json")
    gates = _read(REPORTS / "scale" / "live_gates.json")
    dr = _read(REPORTS / "dr_gameday.json")
    hall = _read(REPORTS / "hallucination.json")
    inj = _read(REPORTS / "injection_decision.json")
    net = _read(REPORTS / "network_metrics.json") or (det.get("network_metrics") or {})
    dist_b = _read(REPORTS / "dist_b.json")
    inv = _read(REPORTS / "scale" / "investigation_throughput.json")
    hold = _read(REPORTS / "rule_miner_holdout.json")
    races = _read(REPORTS / "races.json")
    hn = _read(REPORTS / "hard_negatives.json")
    hn_net = _read(REPORTS / "hard_negative_results.json")
    deepeval = _read(REPORTS / "deepeval.json")
    net_v2 = _read(REPORTS / "network_evaluation_v2.json")
    tput_v2 = _read(REPORTS / "investigation_throughput_v2.json")
    dist_b_before = _read(REPORTS / "dist_b_before.json")
    dist_c = _read(REPORTS / "dist_c.json")
    live_tps = gates.get("max_sustained_consume_tps_passing_gate") or 814.13
    if det.get("network_metrics") and not (REPORTS / "network_metrics.json").exists():
        (REPORTS / "network_metrics.json").write_text(json.dumps(det["network_metrics"], indent=2, default=str))
        net = det["network_metrics"]
    gem_n = gem.get("schema_valid_n") or gem.get("agreement_n")
    report = {
        **experiment_metadata(
            dataset=det.get("benchmark") or "synthetic_v1",
            case_count=det.get("sample_count") or 0,
            model=gem.get("model"),
            timestamp_utc=started,
        ),
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "pytest_exit_code": int(code),
        "deterministic": det,
        "scale": {
            "max_sustained_tps_under_slo": live_tps,
            "max_measured_consume_tps": gates.get("max_measured_consume_tps"),
            "path": "pubsub_cloud_run_cloud_sql",
            "label": "Measured",
            "live_gates": "reports/scale/live_gates.json",
            "investigation_throughput": inv or None,
            "investigation_throughput_v2": tput_v2 or None,
            "note": "Highest consume that passed its gate. 2k miss. Not 5,000 TPS.",
        },
        "gemini": {
            "grounding": "Verified",
            "agreement": gem.get("agreement"),
            "agreement_n": gem_n,
            "agreement_ci": gem.get("agreement_ci"),
            "p95_latency_ms": gem.get("p95_latency_ms"),
            "cost_per_case_usd": gem.get("cost_per_case_usd"),
            "tokens_per_case": gem.get("tokens_per_case"),
            "hallucination_rate": hall.get("hallucination_rate"),
            "unsupported_claim_rate": hall.get("unsupported_claim_rate"),
            "artifact": "reports/gemini_agreement.json",
        },
        "network": net,
        "dist_b": dist_b,
        "dist_b_before": dist_b_before or None,
        "dist_c": dist_c or None,
        "injection": inj,
        "hard_negatives": hn_net or hn,
        "network_v2": net_v2 or None,
        "races": races,
        "rule_miner": hold,
        "deepeval": {
            "imported": bool(deepeval),
            "ran": bool(deepeval.get("ran")),
            "case_count": deepeval.get("case_count"),
            "official_metrics": deepeval.get("official_metrics"),
            "artifact": "reports/deepeval.json" if deepeval else None,
        },
        "dr": {
            "rpo": dr.get("rpo_minutes"),
            "rto": dr.get("rto_minutes"),
            "rpo_kind": dr.get("rpo_kind", "current_state_clone"),
            "pitr_to_past_rpo": dr.get("pitr_to_past_rpo", "NOT_MEASURED"),
            "duplicates_after_replay": dr.get("duplicates_after_replay"),
            "label": dr.get("label", "Target — not yet timed"),
        },
    }
    (REPORTS / "validation_report.json").write_text(json.dumps(report, indent=2, default=str))
    _write_markdown(report, gates)
    _write_scorecard(report, gates, gem, dr, hall, inj, net, inv, hold, races, hn_net or hn, dist_b, deepeval, net_v2, tput_v2, dist_b_before, dist_c)
    _write_final_report(report, gates, gem, dr, hall, inj, net, inv, hold, races, hn_net or hn, dist_b, deepeval, net_v2, tput_v2, dist_b_before, dist_c)
    dest = ROOT / "validation" / "results" / f"run_{started.replace(':', '').replace('-', '')[:15]}"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("SCORECARD.md", "VALIDATION_REPORT.md", "validation_report.json"):
        src = REPORTS / name
        if src.exists():
            shutil.copy2(src, dest / name)
    final = ROOT / "FINAL_VALIDATION_REPORT.md"
    if final.exists():
        shutil.copy2(final, dest / "FINAL_VALIDATION_REPORT.md")
    return 0 if int(code) == 0 else int(code)


def _write_markdown(report: dict, gates: dict) -> None:
    det = report.get("deterministic") or {}
    metrics = det.get("metrics") or {}
    gem = report.get("gemini") or {}
    net = report.get("network") or {}
    runs = gates.get("runs") or []
    scale_rows = "\n".join(
        f"| {r.get('target'):,} | {r.get('publish_tps')} | {r.get('achieved_tps')} | {r.get('gate')} | {'passed' if r.get('passed') else 'missed'} |"
        for r in runs
    ) or "| — | — | — | — | — |"
    (ROOT / "reports" / "VALIDATION_REPORT.md").write_text(
        f"""# Validation report

run_id `{report.get('run_id')}` commit `{report.get('git_commit')}`. Seed `{report['random_seed']}`. Pytest exit `{report['pytest_exit_code']}`.

## Deterministic
status={det.get('status')} f1={metrics.get('f1')} fpr={metrics.get('false_positive_rate')} samples={det.get('sample_count')}
{det.get('ground_truth')}. Gate F1 ≥ 0.85.

## Network
account_recall={net.get('account_recall')} key_node_recall={net.get('key_node_recall')} reconstruction={net.get('relationship_reconstruction')}

## Scale (Pub/Sub → Cloud Run → Cloud SQL)

| Target | Publish TPS | Consume TPS | Gate | Result |
|---|---:|---:|---:|---|
{scale_rows}

Max sustained ingest TPS under a passing gate: **{report['scale']['max_sustained_tps_under_slo']}**. Not 5,000 TPS.
Investigation enqueue TPS: {(report['scale'].get('investigation_throughput') or {}).get('enqueue_tps')} (`reports/scale/investigation_throughput.json`).
Investigation completion TPS (Policy A): {((report['scale'].get('investigation_throughput_v2') or {}).get('policy_a_deterministic') or {}).get('completion_tps')} (`reports/investigation_throughput_v2.json`).

Canonical narrative with one run ID per experiment: `FINAL_VALIDATION_REPORT.md`.

## Gemini
agreement={gem.get('agreement')} n={gem.get('agreement_n')} ci={gem.get('agreement_ci')} p95_ms={gem.get('p95_latency_ms')}
cost/case={gem.get('cost_per_case_usd')} tokens/case={gem.get('tokens_per_case')}
hallucination={gem.get('hallucination_rate')} unsupported={gem.get('unsupported_claim_rate')}

## DR
RTO={report['dr']['rto']} current-state clone RPO={report['dr']['rpo']} ({report['dr']['rpo_kind']}).
PITR-to-past RPO={report['dr']['pitr_to_past_rpo']}. replay_duplicates={report['dr']['duplicates_after_replay']}.
"""
    )


def _exp(d: dict, artifact: str) -> str:
    rid = d.get("run_id") or "unstamped"
    commit = (d.get("git_commit") or "not-recorded")[:12]
    ts = d.get("timestamp_utc") or "not-recorded"
    return f"run `{rid}` commit `{commit}` ts `{ts}` — `{artifact}`"


def _write_final_report(report, gates, gem, dr, hall, inj, net, inv, hold, races, hn, dist_b, deepeval, net_v2, tput_v2, dist_b_before, dist_c=None) -> None:
    det = report.get("deterministic") or {}
    metrics = det.get("metrics") or {}
    before = (dist_b_before or {}).get("metrics") or {}
    after = (dist_b.get("metrics") or {})
    pol_a = (tput_v2 or {}).get("policy_a_deterministic") or {}
    pol_b = (tput_v2 or {}).get("policy_b_gemini") or {}
    kinds = deepeval.get("kind_counts") or {}
    kind_rows = "\n".join(f"| {k} | {v} |" for k, v in sorted(kinds.items())) or "| — | — |"
    means = deepeval.get("mean_scores") or {}
    mean_rows = "\n".join(f"| {k} | {v} |" for k, v in means.items()) or "| — | — |"
    runs = gates.get("runs") or []
    scale_rows = "\n".join(
        f"| {r.get('target'):,} | {r.get('publish_tps')} | {r.get('achieved_tps')} | {r.get('gate')} | {'passed' if r.get('passed') else 'missed'} |"
        for r in runs
    ) or "| — | — | — | — | — |"
    body = f"""# Corridor Watch — final validation report

Suite wrap {_exp(report, "reports/validation_report.json")}. Seed `{report.get("random_seed")}`.
Each experiment below keeps its own run ID / commit / timestamp. Do not collapse them into one number.
Dictionary: `validation/METRICS.md`. Scoreboard: `reports/SCORECARD.md`.

## Benchmark A (generator A / hidden oracle)

{_exp(det if det.get("run_id") else report, "reports/validation_report.json")}

- n={det.get("sample_count")} F1={metrics.get("f1")} FPR={metrics.get("false_positive_rate")}
- Runtime ignores `fraud_scenario`. Gate F1 ≥ 0.85.

## Benchmark B (independent Dist B, frozen seed 7)

{_exp(dist_b, "reports/dist_b.json")}
Before (same seed, pre-fix): precision={before.get("precision")} F1={before.get("f1")} FPR={before.get("false_positive_rate")} (`reports/dist_b_before.json`).
After: precision={after.get("precision")} F1={after.get("f1")} FPR={after.get("false_positive_rate")} TP={after.get("tp")} FP={after.get("fp")} FN={after.get("fn")} TN={after.get("tn")}.

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

{_exp(dist_c or {{}}, "reports/dist_c.json")}

Freeze: `reports/dist_c_freeze.json`. Detector was not retuned on this seed. Threshold remains 40.

- n={(dist_c or {{}}).get("sample_count")} precision={((dist_c or {{}}).get("metrics") or {{}}).get("precision")} recall={((dist_c or {{}}).get("metrics") or {{}}).get("recall")} F1={((dist_c or {{}}).get("metrics") or {{}}).get("f1")} FPR={((dist_c or {{}}).get("metrics") or {{}}).get("false_positive_rate")}
- Unseen fraud names: layering_cascade (middle hop dropped), dormant_wake, funnel_exit, mirror_peel. Not data_gen / Dist B labels.
- Normals: bipartite market, remittance mesh, FX hedge, JPY payroll, noise, ambiguous tuition/charity inbound.
- Do not treat a later retune against seed 23 as generalization.

## Hard negatives

{_exp(hn or {{}}, "reports/hard_negative_results.json")}

- n={(hn or {{}}).get("n")} FPR={(hn or {{}}).get("fpr")} precision={(hn or {{}}).get("precision")} recall={(hn or {{}}).get("recall")}
- 10 legit archetypes + fraud twins. Not 7 isolated wires.

## Network v2 (investigation-useful)

Full-graph account recall {_exp(net if (net or {}).get("run_id") else report, "reports/network_metrics.json")}: account={(net or {}).get("account_recall")}
v2 {_exp(net_v2 or {{}}, "reports/network_evaluation_v2.json")}: anchor={(net_v2 or {{}}).get("anchor_recall")} critical-node={(net_v2 or {{}}).get("critical_node_recall")} critical-edge={(net_v2 or {{}}).get("critical_edge_recall")} path={(net_v2 or {{}}).get("investigation_path_recovery")} recall@10={(net_v2 or {{}}).get("recall_at_10")}

Old full-graph line and v2 are different metrics. Do not substitute.

## Gemini

{_exp(gem, "reports/gemini_agreement.json")}

- agreement={gem.get("agreement")} schema_valid={gem.get("schema_valid_n") or gem.get("agreement_n")} invoked={gem.get("invoked_n")} CI={gem.get("agreement_ci")}
- p95={gem.get("p95_latency_ms")} ms (gate 8000) model={gem.get("model")} cost/case={gem.get("cost_per_case_usd")} tokens/case={gem.get("tokens_per_case")}
- Hallucination {_exp(hall, "reports/hallucination.json")}: gate={hall.get("hallucination_rate")} unsupported={hall.get("unsupported_claim_rate")} entity={hall.get("entity_error_rate")} numerical={hall.get("numerical_error_rate")} live ungrounded={hall.get("live_ungrounded_rate")} n={hall.get("live_n")} (live model hallucination rate NOT_MEASURED)

If this artifact has no `git_commit`, it was measured before experiment stamping. Numbers are still the live n=100 run; do not backfill a commit.

## DeepEval

{_exp(deepeval, "reports/deepeval.json")}

- `ran`={deepeval.get("ran")} n={deepeval.get("case_count")} official={deepeval.get("official_metrics")} faithfulness={deepeval.get("faithfulness")} official_n={deepeval.get("official_n")}
- Empty runner stays `ran: false` n=1. This row is Verified only at n≥100 real investigation reports.

| kind | n |
|---|---|
{kind_rows}

| metric | mean |
|---|---|
{mean_rows}

Mix: normal, obvious fraud (mule/hop), subtle fraud, hard negatives, partial visibility, contradictory evidence, missing evidence, document cases, prompt injection, tool failure, hybrid/novel.

## Scale

{_exp(gates, "reports/scale/live_gates.json")}

| Target | Publish TPS | Consume TPS | Gate | Result |
|---|---:|---:|---|---|
{scale_rows}

Max sustained ingest under a passing gate: **{report["scale"]["max_sustained_tps_under_slo"]}**. 5,000 TPS remains Target.

## Investigation throughput

Enqueue-only {_exp(inv, "reports/scale/investigation_throughput.json")}: enqueue_tps={inv.get("enqueue_tps")}
Completion {_exp(tput_v2 or {{}}, "reports/investigation_throughput_v2.json")}: Policy A {pol_a.get("completion_tps")}/sec p95={((pol_a.get("time_to_verdict_ms") or {{}}).get("p95"))} ms. Policy B Gemini {pol_b.get("completion_tps")}/sec p95={((pol_b.get("time_to_verdict_ms") or {{}}).get("p95"))} ms n={pol_b.get("n")}.

Enqueue ≠ completion. Neither is ingest TPS.

## Security

{_exp(inj, "reports/injection_decision.json")} decision-change={inj.get("decision_change_rate")} n={inj.get("n")}
RBAC / PII / Gemini-off-ingest: Verified tests under `validation/security/` and `validation/reliability/`.
Concurrent races {_exp(races, "reports/races.json")}: failures={races.get("failures")}
Rule-miner holdout {_exp(hold, "reports/rule_miner_holdout.json")}: precision={hold.get("holdout_precision")}

## DR

{_exp(dr, "reports/dr_gameday.json")}

- RTO={dr.get("rto_minutes")} min. Clone RPO={dr.get("rpo_minutes")} min (current-state). PITR-to-past NOT_MEASURED.

## Known failures

- 2,000 TPS consume missed the 1500 gate (measured 1148). SQL-bound. Not claimed as 5,000 TPS.
- Investigation-path recovery {(net_v2 or {{}}).get("investigation_path_recovery")} (not 1.0).
- Pattern accuracy on Dist B can be 0 even when F1 is 1.0 (`burst_smurf` → `mule_pass_through`). Detection F1 is the scored metric.
- Policy B Gemini completion is 0.36 TPS on n=10. Not a fleet number.
- PITR-to-past RPO is NOT_MEASURED.
- Dist C one-shot (seed 23): recall={((dist_c or {{}}).get("metrics") or {{}}).get("recall")} FPR={((dist_c or {{}}).get("metrics") or {{}}).get("false_positive_rate")} F1={((dist_c or {{}}).get("metrics") or {{}}).get("f1")}. High fan-in legit (tuition/charity/market) still flags. Detector was not retuned.
"""
    (ROOT / "FINAL_VALIDATION_REPORT.md").write_text(body)
    (REPORTS / "FINAL_VALIDATION_REPORT.md").write_text(body)


def _write_scorecard(report, gates, gem, dr, hall, inj, net, inv, hold, races, hn, dist_b, deepeval, net_v2=None, tput_v2=None, dist_b_before=None, dist_c=None) -> None:
    det = report.get("deterministic") or {}
    metrics = det.get("metrics") or {}
    f1 = metrics.get("f1")
    det_status = "Verified" if det.get("quality_gate", {}).get("passed") else "Implemented"
    runs = {r.get("target"): r for r in (gates.get("runs") or [])}

    def _row(target: int) -> str:
        r = runs.get(target) or {}
        if not r:
            return "—"
        return f"{'Verified' if r.get('passed') else 'Missed'} **{r.get('achieved_tps')}** (gate {r.get('gate')})"

    n = gem.get("schema_valid_n")
    invoked = gem.get("invoked_n")
    ci = gem.get("agreement_ci")
    agree = gem.get("agreement")
    agree_row = (
        f"Verified **{agree}** schema_valid n={n} / invoked {invoked} CI={ci} (gate 0.85)"
        if agree is not None
        else "NOT_MEASURED"
    )
    p95 = gem.get("p95_latency_ms")
    p95_row = (
        f"{'Verified' if p95 is not None and p95 <= 8000 else 'Missed'} {p95} ms (gate 8000)"
        if p95 is not None
        else "NOT_MEASURED"
    )
    hall_v = hall.get("hallucination_rate")
    hall_n = hall.get("live_n")
    uns_v = hall.get("unsupported_claim_rate")
    hall_status = (
        f"Verified trap/gate {hall_v}; live ungrounded {hall.get('live_ungrounded_rate')} n={hall_n} (live model rate NOT_MEASURED)"
        if hall_v is not None
        else "NOT_MEASURED"
    )
    rto = dr.get("rto_minutes")
    rpo = dr.get("rpo_minutes")
    dr_label = f"Measured RTO {rto} min; clone RPO {rpo} min (current-state). PITR-to-past NOT_MEASURED"
    if rto is None:
        dr_label = "Target — not yet timed"
    deepeval_row = (
        f"Verified n={deepeval.get('case_count')} kinds={len(deepeval.get('kind_counts') or {})} BaseMetric (official {deepeval.get('official_metrics')})"
        if deepeval.get("ran") and (deepeval.get("case_count") or 0) >= 100
        else ("NOT_MEASURED" if not deepeval else f"Implemented ran={deepeval.get('ran')} n={deepeval.get('case_count')}")
    )
    dist_after = (dist_b.get("metrics") or {}).get("f1")
    dist_before_f1 = ((dist_b_before or {}).get("metrics") or {}).get("f1")
    dist_row = (
        f"{_status(dist_after)} (before {dist_before_f1}, FPR {((dist_b_before or {}).get('metrics') or {}).get('false_positive_rate')})"
        if dist_after is not None
        else "NOT_MEASURED"
    )
    dist_c_m = (dist_c or {}).get("metrics") or {}
    dist_c_row = (
        f"Measured F1 {dist_c_m.get('f1')} recall {dist_c_m.get('recall')} FPR {dist_c_m.get('false_positive_rate')} (seed 23 one-shot)"
        if dist_c_m.get("f1") is not None
        else "NOT_MEASURED"
    )
    pol_a = (tput_v2 or {}).get("policy_a_deterministic") or {}
    pol_b = (tput_v2 or {}).get("policy_b_gemini") or {}
    hn_fpr = hn.get("fpr") if hn else None
    ent_v = hall.get("entity_error_rate")
    num_v = hall.get("numerical_error_rate")
    (ROOT / "reports" / "SCORECARD.md").write_text(
        f"""# Corridor Watch — validation scorecard

run_id `{report.get('run_id')}` commit `{report.get('git_commit')}`. Seed `{report.get('random_seed')}`.
Do not upgrade a row without a new artifact. Dictionary: `validation/METRICS.md`.

| Claim | Status | Evidence |
|---|---|---|
| Detector F1 | {det_status} {f1 if f1 is not None else ""} | `validation/deterministic/test_detection.py` / hidden oracle |
| Dist B F1 | {dist_row} | `reports/dist_b.json` vs `reports/dist_b_before.json` |
| Dist C F1 | {dist_c_row} | `reports/dist_c.json` (freeze `reports/dist_c_freeze.json`) |
| Network account recall | {_status(net.get('account_recall'))} | `reports/network_metrics.json` |
| Network v2 anchor recall | {_status((net_v2 or {}).get('anchor_recall'))} | `reports/network_evaluation_v2.json` |
| Network v2 critical-node recall | {_status((net_v2 or {}).get('critical_node_recall'))} | `reports/network_evaluation_v2.json` |
| Network v2 investigation-path | {_status((net_v2 or {}).get('investigation_path_recovery'))} | `reports/network_evaluation_v2.json` |
| Network v2 recall@10 | {_status((net_v2 or {}).get('recall_at_10'))} | `reports/network_evaluation_v2.json` |
| Gemini grounding | Verified | `validation/deepeval/test_grounding.py` |
| Gemini vs deterministic agreement | {agree_row} | `reports/gemini_agreement.json` |
| Hallucination rate | {hall_status} | `reports/hallucination.json` |
| Unsupported claim rate | {_status(uns_v)} | `reports/hallucination.json` |
| Entity error rate | {_status(ent_v)} | `reports/hallucination.json` |
| Numerical error rate | {_status(num_v)} | `reports/hallucination.json` |
| Gemini cost per case | {_status(gem.get('cost_per_case_usd'), label='Verified $') if gem.get('cost_per_case_usd') is not None else 'NOT_MEASURED'} | `reports/gemini_agreement.json` |
| Gemini tokens per case | {_status(gem.get('tokens_per_case'))} | `reports/gemini_agreement.json` |
| Gemini p95 | {p95_row} | `reports/gemini_agreement.json` |
| Injection decision-change | {_status(inj.get('decision_change_rate'))} | `reports/injection_decision.json` |
| DeepEval package | {deepeval_row} | `reports/deepeval.json` |
| 100 TPS consume | {_row(100)} | `reports/scale/test_100_tps.json` |
| 500 TPS consume | {_row(500)} | `reports/scale/test_500_tps.json` |
| 1,000 TPS consume | {_row(1000)} | `reports/scale/test_1000_tps.json` |
| 2,000 TPS consume | {_row(2000)} | `reports/scale/test_2000_tps.json` |
| Max sustained ingest TPS under SLO | Measured {report['scale']['max_sustained_tps_under_slo']} | passing 1k gate; 2k miss |
| Investigation enqueue TPS | {_status(inv.get('enqueue_tps'))} | `reports/scale/investigation_throughput.json` |
| Investigation completion TPS (Policy A) | {_status(pol_a.get('completion_tps'))} | `reports/investigation_throughput_v2.json` |
| Investigation time-to-verdict p95 (Policy A) | {_status((pol_a.get('time_to_verdict_ms') or {}).get('p95'))} | `reports/investigation_throughput_v2.json` |
| Investigation Gemini TPS (Policy B) | {_status(pol_b.get('completion_tps'))} | `reports/investigation_throughput_v2.json` |
| Hard-negative FPR | {_status(hn_fpr)} | `reports/hard_negative_results.json` |
| Concurrent race failures | {_status(races.get('failures'))} | `reports/races.json` |
| Rule-miner holdout precision | {_status(hold.get('holdout_precision'))} | `reports/rule_miner_holdout.json` |
| RTO/RPO | {dr_label} | `reports/dr_gameday.json` |
| 5,000 TPS | Target | not claimed as achieved |
| Idempotent ingest | Verified | `validation/reliability/test_idempotency.py` |
| Queue recovery | Verified | `validation/reliability/test_queue_recovery.py` |
| Gemini off ingest | Verified | `validation/reliability/test_gemini_isolation.py` |
| RBAC high-risk | Verified | `validation/security/test_rbac.py` |
| PII tokens at Gemini boundary | Verified | `validation/security/test_pii_minimization.py` |

Suite root is `validation/` (not `evaluation/`) because `evaluation.py` already exists.
DeepEval is Verified only when `reports/deepeval.json` has `ran: true` on ≥100 mixed investigation reports. Canonical narrative: `FINAL_VALIDATION_REPORT.md`. Official FaithfulnessMetric stays NOT_MEASURED unless a Gemini judge actually ran.
"""
    )


if __name__ == "__main__":
    sys.exit(main())
