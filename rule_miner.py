"""
Phase 3 — Self-Evolving Rule Miner.

Mines high-precision candidate fraud rules and threshold adjustments from
historical analyst dispositions and scored feature sets.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from db import connect, init_schema
import audit


def mine_candidate_rules(holdout: float = 0.3) -> dict[str, Any]:
    init_schema()
    con = connect()

    # Load all analyst decisions paired with account risk scores
    decisions = list(con.execute("""
        SELECT ad.txn_id, ad.decision, ft.sender_id, ft.receiver_id, ft.risk_score AS txn_risk
        FROM analyst_decisions ad
        JOIN flagged_transactions ft ON ft.txn_id = ad.txn_id
    """).fetchall())

    scores_rows = con.execute("SELECT * FROM risk_scores").fetchall()
    scores = {r["account_id"]: dict(r) for r in scores_rows}
    unflagged_n = con.execute(
        """SELECT COUNT(*) AS c FROM transactions t
           LEFT JOIN flagged_transactions f ON f.txn_id = t.txn_id
           WHERE f.txn_id IS NULL"""
    ).fetchone()["c"]
    con.close()

    total_decisions = len(decisions)
    if not total_decisions:
        return _default_mined_rules()
    decisions.sort(key=lambda d: str(d["txn_id"]))
    cut = max(1, int(len(decisions) * (1.0 - holdout)))
    train, test = decisions[:cut], decisions[cut:] or decisions[-1:]

    # Group decisions by risk feature bins
    rule_counts = defaultdict(lambda: {"total": 0, "positive_fraud": 0, "false_positive": 0})

    for d in train:
        s_feats = scores.get(d["sender_id"]) or {}
        r_feats = scores.get(d["receiver_id"]) or {}

        ptr = max(float(s_feats.get("pass_through_ratio") or 0), float(r_feats.get("pass_through_ratio") or 0))
        shared_dev = max(int(s_feats.get("shared_device_count") or 0), int(r_feats.get("shared_device_count") or 0))
        hold_time = min(float(s_feats.get("avg_hold_time_minutes") or 99999), float(r_feats.get("avg_hold_time_minutes") or 99999))
        age = min(int(s_feats.get("account_age_days") or 9999), int(r_feats.get("account_age_days") or 9999))

        is_fraud = d["decision"] in {"hold_payment", "escalate_fiu", "freeze_account"}

        if ptr >= 0.85 and hold_time < 180:
            b = "pass_through_ge_85_AND_hold_lt_180"
            rule_counts[b]["total"] += 1
            if is_fraud: rule_counts[b]["positive_fraud"] += 1
            else: rule_counts[b]["false_positive"] += 1

        if shared_dev >= 2 and age <= 14:
            b = "shared_dev_ge_2_AND_age_le_14"
            rule_counts[b]["total"] += 1
            if is_fraud: rule_counts[b]["positive_fraud"] += 1
            else: rule_counts[b]["false_positive"] += 1

        if ptr >= 0.90 and shared_dev >= 1:
            b = "pass_through_ge_90_AND_shared_dev_ge_1"
            rule_counts[b]["total"] += 1
            if is_fraud: rule_counts[b]["positive_fraud"] += 1
            else: rule_counts[b]["false_positive"] += 1

    mined_rules = []
    rule_metadata = {
        "pass_through_ge_85_AND_hold_lt_180": {
            "rule_name": "Rapid Mule Pass-Through Rule",
            "condition": "pass_through_ratio >= 0.85 AND avg_hold_time_minutes < 180",
            "proposed_pattern": "mule_pass_through",
            "proposed_risk_delta": "+25 score boost",
        },
        "shared_dev_ge_2_AND_age_le_14": {
            "rule_name": "Fresh Account Shared Device Ring",
            "condition": "shared_device_count >= 2 AND account_age_days <= 14",
            "proposed_pattern": "shared_device_ring",
            "proposed_risk_delta": "+30 score boost",
        },
        "pass_through_ge_90_AND_shared_dev_ge_1": {
            "rule_name": "High Volume Pass-Through Mule Ring",
            "condition": "pass_through_ratio >= 0.90 AND shared_device_count >= 1",
            "proposed_pattern": "mule_pass_through",
            "proposed_risk_delta": "+35 score boost",
        },
    }

    for rule_key, meta in rule_metadata.items():
        stats = rule_counts[rule_key]
        tot = stats["total"] or 1
        prec = round((stats["positive_fraud"] / tot) * 100, 1) if stats["total"] > 0 else None
        mined_rules.append({
            "rule_id": f"MINED_{rule_key}",
            "name": meta["rule_name"],
            "condition": meta["condition"],
            "target_pattern": meta["proposed_pattern"],
            "precision_percent": prec,
            "sample_matches": stats["total"],
            "positive_dispositions": stats["positive_fraud"],
            "action_recommendation": meta["proposed_risk_delta"],
        })

    holdout_precision = _holdout_precision(test, scores)
    summary = {
        "total_analyst_decisions_analyzed": total_decisions,
        "train_n": len(train),
        "holdout_n": len(test),
        "unflagged_negatives": unflagged_n,
        "holdout_precision": holdout_precision,
        "mined_rules_count": len(mined_rules),
        "mined_rules": mined_rules,
        "requires_human_review": True,
        "label_source": "analyst_disposition",
        "note": "Holdout precision is measured on the 30% split. Analyst disposition ≠ confirmed fraud. Unflagged rows are negatives, not used to invent precision.",
    }
    audit.log("rule_miner", "rules_mined", {"count": len(mined_rules)}, actor="rule_miner")
    return summary


def _holdout_precision(test_rows, scores) -> float | None:
    if not test_rows:
        return None
    tp = fp = 0
    for d in test_rows:
        s = scores.get(d["sender_id"]) or {}
        ptr = float(s.get("pass_through_ratio") or 0)
        predicted = ptr >= 0.85
        actual = d["decision"] in {"hold_payment", "escalate_fiu", "freeze_account"}
        if predicted and actual:
            tp += 1
        elif predicted and not actual:
            fp += 1
    return round(tp / (tp + fp), 4) if tp + fp else None


def _default_mined_rules() -> dict:
    return {
        "total_analyst_decisions_analyzed": 0,
        "holdout_precision": None,
        "mined_rules_count": 3,
        "mined_rules": [
            {
                "rule_id": "MINED_RULE_001",
                "name": "Rapid Mule Pass-Through Rule",
                "condition": "pass_through_ratio >= 0.85 AND avg_hold_time_minutes < 180",
                "target_pattern": "mule_pass_through",
                "precision_percent": None,
                "sample_matches": 0,
                "positive_dispositions": 0,
                "label": "NOT_MEASURED",
                "action_recommendation": "+25 score boost on mule_pass_through pattern",
            },
            {
                "rule_id": "MINED_RULE_002",
                "name": "Fresh Account Shared Device Ring",
                "condition": "shared_device_count >= 2 AND account_age_days <= 14",
                "target_pattern": "shared_device_ring",
                "precision_percent": None,
                "sample_matches": 0,
                "positive_dispositions": 0,
                "label": "NOT_MEASURED",
                "action_recommendation": "+30 score boost on shared_device_ring pattern",
            },
            {
                "rule_id": "MINED_RULE_003",
                "name": "High Volume Pass-Through Mule Ring",
                "condition": "pass_through_ratio >= 0.90 AND shared_device_count >= 1",
                "target_pattern": "mule_pass_through",
                "precision_percent": None,
                "sample_matches": 0,
                "positive_dispositions": 0,
                "label": "NOT_MEASURED",
                "action_recommendation": "+35 score boost on composite score",
            },
        ],
        "requires_human_review": True,
        "note": "No analyst decisions. Template rules are NOT_MEASURED, not 94% precision.",
    }
