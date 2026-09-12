"""
Phase 3 — Counterfactual "What-If" Risk Sensitivity Simulator.

Evaluates risk score deltas by dynamically perturbing feature inputs
(e.g. account age, hold time, shared devices, pass-through ratio)
to reveal exact decision boundaries for analysts and model risk auditors.
"""
from __future__ import annotations

from typing import Any

from db import connect
import audit
from graph_features import pattern_scores, composite_score


def simulate_counterfactual(txn_id: str, overrides: dict[str, Any]) -> dict[str, Any]:
    con = connect()
    txn = con.execute("SELECT * FROM flagged_transactions WHERE txn_id=?", (txn_id,)).fetchone()
    if not txn:
        txn = con.execute("SELECT * FROM transactions WHERE txn_id=?", (txn_id,)).fetchone()
    if not txn:
        con.close()
        raise ValueError(f"transaction {txn_id} not found")
    txn = dict(txn)

    sender_acc = con.execute("SELECT * FROM accounts WHERE account_id=?", (txn["sender_id"],)).fetchone()
    sender_risk = con.execute("SELECT * FROM risk_scores WHERE account_id=?", (txn["sender_id"],)).fetchone()
    con.close()

    acc = dict(sender_acc) if sender_acc else {}
    risk_feats = dict(sender_risk) if sender_risk else {
        "fan_in_count": 1,
        "fan_out_count": 1,
        "pass_through_ratio": 0.5,
        "avg_hold_time_minutes": 1440.0,
        "shared_device_count": 0,
        "shared_beneficiary_count": 0,
        "multi_hop_chain_depth": 0,
        "account_age_days": 180,
        "corridor_velocity_score": 1.0,
        "behavioral_risk": 10.0,
    }

    # Compute baseline
    baseline_patterns = pattern_scores(risk_feats, acc)
    baseline_score, baseline_pattern = composite_score(risk_feats, baseline_patterns)

    # Apply feature overrides
    perturbed_feats = dict(risk_feats)
    applied_overrides = {}
    for key, val in overrides.items():
        if key in perturbed_feats and val is not None:
            try:
                perturbed_feats[key] = type(perturbed_feats[key])(val)
                applied_overrides[key] = {"baseline": risk_feats[key], "perturbed": perturbed_feats[key]}
            except (ValueError, TypeError):
                pass

    perturbed_patterns = pattern_scores(perturbed_feats, acc)
    perturbed_score, perturbed_pattern = composite_score(perturbed_feats, perturbed_patterns)

    delta = round(perturbed_score - baseline_score, 1)

    # Feature sensitivity analysis: evaluate single-variable impact
    sensitivities = []
    test_specs = [
        ("account_age_days", 365, "Age increased to 1 year"),
        ("pass_through_ratio", 0.1, "Pass-through reduced to 10%"),
        ("avg_hold_time_minutes", 1440, "Hold time increased to 24 hours"),
        ("shared_device_count", 0, "Shared devices cleared to 0"),
        ("behavioral_risk", 0, "Behavioral risk cleared to 0"),
    ]
    for feat_key, test_val, label in test_specs:
        temp_feats = dict(risk_feats)
        temp_feats[feat_key] = test_val
        temp_p = pattern_scores(temp_feats, acc)
        temp_score, _ = composite_score(temp_feats, temp_p)
        score_impact = round(temp_score - baseline_score, 1)
        sensitivities.append({
            "feature": feat_key,
            "perturbation": label,
            "impact_delta": score_impact,
            "sensitivity": "HIGH" if abs(score_impact) >= 20 else ("MEDIUM" if abs(score_impact) >= 8 else "LOW"),
        })
    sensitivities.sort(key=lambda x: abs(x["impact_delta"]), reverse=True)

    result = {
        "txn_id": txn_id,
        "baseline": {
            "risk_score": baseline_score,
            "primary_pattern": baseline_pattern,
            "features": {k: risk_feats.get(k) for k in applied_overrides},
            "pattern_scores": baseline_patterns,
        },
        "counterfactual": {
            "risk_score": perturbed_score,
            "primary_pattern": perturbed_pattern,
            "applied_overrides": applied_overrides,
            "pattern_scores": perturbed_patterns,
        },
        "score_delta": delta,
        "risk_level_change": (
            "INCREASED" if delta > 5 else ("DECREASED" if delta < -5 else "UNCHANGED")
        ),
        "sensitivity_rankings": sensitivities,
    }
    audit.log(txn_id, "counterfactual_sim", {"delta": delta}, actor="counterfactual")
    return result
