"""Deterministic evaluation harness for the synthetic benchmark.

The benchmark uses the generator's fraud_scenario labels as ground truth. It is
intentionally independent of Gemini so model availability cannot inflate the
core detection metrics. The output is suitable for a demo scorecard and CI.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

from db import connect, init_schema
from investigation_dag import run_dag

POSITIVE_SCENARIOS = {
    "mule_pass_through",
    "split_transaction_laundering",
    "shared_device_ring",
    "synthetic_identity",
    "multi_hop_chain",
}


def _binary_metrics(y_true: list[bool], y_pred: list[bool]) -> dict[str, float | int]:
    tp = sum(a and b for a, b in zip(y_true, y_pred))
    fp = sum((not a) and b for a, b in zip(y_true, y_pred))
    fn = sum(a and (not b) for a, b in zip(y_true, y_pred))
    tn = sum((not a) and (not b) for a, b in zip(y_true, y_pred))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fp / (fp + tn), 4) if fp + tn else 0.0,
    }


def run_evaluation(include_trace: bool = False) -> dict[str, Any]:
    init_schema()
    con = connect()
    rows = [dict(r) for r in con.execute(
        "SELECT * FROM transactions ORDER BY txn_id"
    ).fetchall()]
    con.close()

    if not rows:
        return {"status": "no_data", "message": "Generate the synthetic dataset first."}

    y_true: list[bool] = []
    y_pred: list[bool] = []
    by_scenario: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "flagged": 0})
    pattern_confusion: Counter[tuple[str, str]] = Counter()
    positive_total = 0
    pattern_correct = 0
    examples = []

    # Core benchmark is based on the deterministic graph/rule detector.
    for txn in rows:
        bundle = run_dag(txn["txn_id"], audit_events=False)
        verdict = bundle["verdict"]
        truth = txn.get("fraud_scenario") in POSITIVE_SCENARIOS
        predicted = float(verdict.get("risk_score", 0)) >= 40
        y_true.append(truth)
        y_pred.append(predicted)
        scenario = txn.get("fraud_scenario") or "normal"
        predicted_pattern = verdict.get("primary_pattern")
        if truth:
            positive_total += 1
            pattern_correct += int(predicted_pattern == scenario)
            pattern_confusion[(scenario, predicted_pattern)] += 1
        by_scenario[scenario]["total"] += 1
        by_scenario[scenario]["flagged"] += int(predicted)
        if include_trace and len(examples) < 20:
            examples.append({
                "txn_id": txn["txn_id"],
                "truth": scenario,
                "predicted_risk": verdict.get("risk_score"),
                "predicted_pattern": verdict.get("primary_pattern"),
            })

    metrics = _binary_metrics(y_true, y_pred)
    per_scenario = {}
    for scenario, stats in sorted(by_scenario.items()):
        per_scenario[scenario] = {
            **stats,
            "flag_rate": round(stats["flagged"] / stats["total"], 4) if stats["total"] else 0.0,
        }

    result = {
        "status": "ok",
        "benchmark": "synthetic_v1",
        "ground_truth": "transactions.fraud_scenario",
        "positive_scenarios": sorted(POSITIVE_SCENARIOS),
        "sample_count": len(rows),
        "metrics": metrics,
        "per_scenario": per_scenario,
        "pattern_accuracy": round(pattern_correct / positive_total, 4) if positive_total else 0.0,
        "pattern_confusion": {f"{truth}->{pred}": n for (truth, pred), n in sorted(pattern_confusion.items())},
        "quality_gate": {
            "minimum_recall": 0.90,
            "minimum_precision": 0.50,
            "minimum_pattern_accuracy": 0.90,
            "passed": (metrics["recall"] >= 0.90 and metrics["precision"] >= 0.50
                       and (pattern_correct / positive_total if positive_total else 0.0) >= 0.90),
        },
    }
    if include_trace:
        result["examples"] = examples
    return result


def benchmark_summary() -> str:
    result = run_evaluation()
    return json.dumps(result, indent=2)
