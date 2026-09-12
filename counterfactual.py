"""
Phase 3 — Counterfactual "What-If" Risk Sensitivity Simulator.

Evaluates risk score deltas by dynamically perturbing feature inputs
(e.g. account age, hold time, shared devices, pass-through ratio)
to reveal exact decision boundaries for analysts and model risk auditors.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from db import connect
import audit
from graph_features import pattern_scores, composite_score

FEATURE_DEFAULTS = {
    "fan_in_count": 0,
    "fan_out_count": 0,
    "pass_through_ratio": 0.0,
    "avg_hold_time_minutes": 1440.0,
    "shared_device_count": 0,
    "shared_beneficiary_count": 0,
    "multi_hop_chain_depth": 0,
    "account_age_days": 1,
    "corridor_velocity_score": 0.0,
    "behavioral_risk": 0.0,
}


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _coerce_features(raw: dict | None) -> dict[str, Any]:
    source = dict(raw or {})
    out: dict[str, Any] = {}
    for key, default in FEATURE_DEFAULTS.items():
        val = source.get(key, default)
        if val is None:
            val = default
        try:
            out[key] = type(default)(val)
        except (TypeError, ValueError):
            out[key] = default
    return out


def _stored_features_usable(row: dict | None) -> bool:
    if not row:
        return False
    if row.get("fan_in_count") is None and row.get("pass_through_ratio") is None:
        return False
    return True


def _derive_from_ledger(con, account_id: str, txn: dict, acc: dict) -> dict[str, Any]:
    rows = con.execute(
        """SELECT txn_id, sender_id, receiver_id, amount, ts, device_id, beneficiary_id
           FROM transactions
           WHERE sender_id=? OR receiver_id=?
           ORDER BY ts DESC LIMIT 80""",
        (account_id, account_id),
    ).fetchall()
    ledger = [dict(r) for r in rows]
    inbound = [t for t in ledger if t["receiver_id"] == account_id]
    outbound = [t for t in ledger if t["sender_id"] == account_id]
    in_amt = sum(float(t.get("amount") or 0) for t in inbound)
    out_amt = sum(float(t.get("amount") or 0) for t in outbound)
    ptr = min(out_amt / in_amt, 1.5) if in_amt > 0 else 0.0

    times = [t for t in (_parse_ts(x.get("ts")) for x in ledger) if t]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    opened = _parse_ts(acc.get("opened_date"))
    if opened:
        age = max(0, (now - opened).days)
    elif times:
        age = max(0, (now - min(times)).days)
    else:
        age = 1

    in_times = sorted(t for t in (_parse_ts(x.get("ts")) for x in inbound) if t)
    out_times = sorted(t for t in (_parse_ts(x.get("ts")) for x in outbound) if t)
    holds: list[float] = []
    for ot in out_times:
        prior = [it for it in in_times if it <= ot]
        if prior:
            holds.append((ot - max(prior)).total_seconds() / 60.0)
    hold = sum(holds) / len(holds) if holds else 1440.0

    device_peers: dict[str, set[str]] = {}
    for t in ledger:
        did = t.get("device_id")
        if did:
            device_peers.setdefault(str(did), set()).add(t["sender_id"])
    shared_dev = len({
        peer
        for peers in device_peers.values()
        if account_id in peers
        for peer in peers
        if peer != account_id
    })
    extra = con.execute(
        """SELECT COUNT(DISTINCT ad2.account_id) AS c
           FROM account_devices ad
           JOIN account_devices ad2 ON ad2.device_id = ad.device_id
           WHERE ad.account_id=? AND ad2.account_id != ?""",
        (account_id, account_id),
    ).fetchone()
    if extra is not None:
        shared_dev = max(shared_dev, int(extra["c"] or 0))

    benef_peers = con.execute(
        """SELECT COUNT(DISTINCT ab2.account_id) AS c
           FROM account_beneficiaries ab
           JOIN account_beneficiaries ab2 ON ab2.beneficiary_id = ab.beneficiary_id
           WHERE ab.account_id=? AND ab2.account_id != ?""",
        (account_id, account_id),
    ).fetchone()
    shared_ben = int(benef_peers["c"] or 0) if benef_peers is not None else 0

    vel = 0.0
    if len(times) >= 2:
        span_h = max((max(times) - min(times)).total_seconds() / 3600.0, 0.25)
        vel = len(times) / span_h

    beh = 0.0
    sessions = con.execute(
        """SELECT bot_likelihood, copy_paste_risk, typing_deviation,
                  navigation_velocity, geo_mismatch
           FROM sessions WHERE account_id=? LIMIT 5""",
        (account_id,),
    ).fetchall()
    if sessions:
        scores = []
        for s in sessions:
            row = dict(s)
            scores.append(
                float(row.get("bot_likelihood") or 0) * 40
                + float(row.get("copy_paste_risk") or 0) * 25
                + min(float(row.get("typing_deviation") or 0), 4) * 5
                + min(float(row.get("navigation_velocity") or 0), 6) * 3
                + (15 if row.get("geo_mismatch") else 0)
            )
        beh = round(min(max(scores), 100), 1)
    elif (txn.get("fraud_scenario") or "normal") not in {"", "normal"}:
        beh = 35.0

    hop = 0
    if inbound and outbound:
        hop = 1
    if len({t["receiver_id"] for t in outbound}) >= 2:
        hop = max(hop, 2)

    return {
        "fan_in_count": len(inbound),
        "fan_out_count": len(outbound),
        "pass_through_ratio": round(ptr, 2),
        "avg_hold_time_minutes": round(hold, 1),
        "shared_device_count": int(shared_dev),
        "shared_beneficiary_count": shared_ben,
        "multi_hop_chain_depth": hop,
        "account_age_days": int(age),
        "corridor_velocity_score": round(vel, 2),
        "behavioral_risk": float(beh),
    }


def features_for_case(txn_id: str) -> dict[str, Any]:
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
    acc = dict(sender_acc) if sender_acc else {}
    stored = dict(sender_risk) if sender_risk else None
    if _stored_features_usable(stored):
        feats = _coerce_features(stored)
    else:
        feats = _coerce_features(_derive_from_ledger(con, txn["sender_id"], txn, acc))
    con.close()
    return feats


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
    acc = dict(sender_acc) if sender_acc else {}
    stored = dict(sender_risk) if sender_risk else None
    if _stored_features_usable(stored):
        risk_feats = _coerce_features(stored)
        feature_source = "risk_scores"
    else:
        risk_feats = _coerce_features(_derive_from_ledger(con, txn["sender_id"], txn, acc))
        feature_source = "live_neighborhood"
    con.close()

    baseline_patterns = pattern_scores(risk_feats, acc)
    baseline_score, baseline_pattern = composite_score(risk_feats, baseline_patterns)

    perturbed_feats = dict(risk_feats)
    applied_overrides = {}
    for key, val in overrides.items():
        if key not in FEATURE_DEFAULTS or val is None:
            continue
        try:
            coerced = type(FEATURE_DEFAULTS[key])(val)
        except (ValueError, TypeError):
            continue
        applied_overrides[key] = {"baseline": risk_feats[key], "perturbed": coerced}
        perturbed_feats[key] = coerced

    perturbed_patterns = pattern_scores(perturbed_feats, acc)
    perturbed_score, perturbed_pattern = composite_score(perturbed_feats, perturbed_patterns)

    delta = round(perturbed_score - baseline_score, 1)

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
        "feature_source": feature_source,
        "case_risk_score": txn.get("risk_score"),
        "baseline": {
            "risk_score": baseline_score,
            "primary_pattern": baseline_pattern,
            "features": risk_feats,
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
    audit.log(txn_id, "counterfactual_sim", {"delta": delta, "source": feature_source}, actor="counterfactual")
    return result
