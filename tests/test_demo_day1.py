"""Day-1 hackathon demo claims: risk consistency, Gemini payload, Pattern DNA next alert."""
from __future__ import annotations

import json

from patterns.extractor import extract_from_confirmation
from patterns.matcher import match_patterns
from patterns.repository import list_patterns
from privacy import minimize_txn, token_for
from synthetic.middle_bank import HERO_TXN_ID, seed_middle_bank


def test_cw_mid_02_risk_is_single_source(isolated_db):
    seed_middle_bank()
    from db import connect

    con = connect()
    txn = con.execute("SELECT risk_score FROM transactions WHERE txn_id=?", (HERO_TXN_ID,)).fetchone()
    flagged = con.execute(
        "SELECT risk_score FROM flagged_transactions WHERE txn_id=?", (HERO_TXN_ID,)
    ).fetchone()
    account = con.execute(
        "SELECT risk_score, corridor_velocity_score FROM risk_scores WHERE account_id=?",
        ("ACC-MID-SG-MULE",),
    ).fetchone()
    con.close()
    assert txn["risk_score"] == flagged["risk_score"] == 91
    assert account["risk_score"] == 91
    # Corridor velocity is a separate feature — not the alert risk.
    assert account["corridor_velocity_score"] == 84


def test_grounded_payload_has_no_raw_account_ids():
    """Mirror the payload keys built in grounded_gemini_report."""
    txn = {
        "txn_id": "CW-MID-02",
        "sender_id": "ACC-MID-SG-MULE",
        "receiver_id": "ACC-MID-PH-EXIT",
        "amount": 9050,
        "corridor": "SG->PH",
        "name": "Harbour Relay Pte",
    }
    payload = {
        "transaction": minimize_txn(txn),
        "account_risk": {"risk_score": 91, "primary_pattern": "mule_pass_through"},
    }
    blob = json.dumps(payload)
    assert "ACC-MID-SG-MULE" not in blob
    assert "ACC-MID-PH-EXIT" not in blob
    assert "Harbour Relay" not in blob
    assert payload["transaction"]["sender_account"] == token_for("ACC-MID-SG-MULE", "account")


def test_confirm_then_next_alert_matches(isolated_db):
    seed_middle_bank()
    before = {p.pattern_id: p.confirmed_cases for p in list_patterns()}
    txn = {
        "txn_id": "CW-MID-02",
        "sender_id": "ACC-MID-SG-MULE",
        "receiver_id": "ACC-MID-PH-EXIT",
        "corridor": "SG->PH",
        "fraud_scenario": "mule_pass_through",
        "primary_pattern": "mule_pass_through",
    }
    network = {
        "features": {
            "fan_in": 6,
            "fan_out": 2,
            "shared_device_groups": 1,
            "shared_beneficiary_groups": 0,
            "cross_border": 2,
            "institution_count": 3,
            "txn_count": 8,
        }
    }
    risk = {
        "account_age_days": 16,
        "pass_through_ratio": 0.98,
        "avg_hold_time_minutes": 18,
        "shared_device_count": 1,
    }
    pattern = extract_from_confirmation(txn, network, risk, "escalate_fiu", created_by="fiu_lead")
    assert pattern is not None
    after = {p.pattern_id: p.confirmed_cases for p in list_patterns()}
    assert after.get(pattern.pattern_id, 0) >= before.get(pattern.pattern_id, 0)

    next_txn = {
        "txn_id": "CW-MID-03",
        "sender_id": "ACC-MID-SG-MULE",
        "receiver_id": "ACC-MID-PH-EXIT",
        "corridor": "SG->PH",
        "fraud_scenario": "mule_pass_through",
    }
    matches = match_patterns(next_txn, network, risk, persist=True)
    assert matches
    assert float(matches[0]["match_strength"]) > 0
    from db import connect

    con = connect()
    stored = con.execute(
        "SELECT COUNT(*) AS c FROM pattern_matches WHERE txn_id=?", ("CW-MID-03",)
    ).fetchone()["c"]
    con.close()
    assert stored >= 1


def test_demo_seed_has_five_cases_three_typologies(isolated_db):
    from synthetic.showcase import seed_showcase

    seed_showcase()
    seed_middle_bank()
    from db import connect

    con = connect()
    rows = con.execute(
        "SELECT txn_id, fraud_scenario, risk_score FROM flagged_transactions ORDER BY txn_id"
    ).fetchall()
    con.close()
    ids = {r["txn_id"] for r in rows}
    scenarios = {r["fraud_scenario"] for r in rows}
    assert len(ids) >= 5
    assert len(scenarios) >= 3
    assert "CW-MID-02" in ids and "CW-MID-03" in ids
