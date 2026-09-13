"""Deterministic middle-bank partial-visibility campaign.

Corridor Watch is BANK_SG. Observed hops: BANK_IN -> BANK_SG -> BANK_PH.
Bank D and the off-ramp stay unknown until synthetic intelligence is applied.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db import connect, init_schema, upsert
from pubsub.schemas import utc_now

NETWORK_ID = "NET-MIDDLE-BANK"
HERO_TXN_ID = "CW-MID-02"
DEVICE_ID = "D-MID-MULE"
SHOWCASE_FLAG = "middle_bank"

ACCOUNTS = [
    {
        "account_id": "ACC-MID-IN-FEED",
        "name": "N. Kapoor Disbursements",
        "country": "IN",
        "opened_date": "2025-10-12",
        "occupation": "payroll clerk",
        "stated_income_usd": 6400,
        "kyc_tier": "standard",
        "fraud_label": "split_transaction_laundering",
        "bank_id": "BANK_IN",
        "customer_id": "CUS-MID-IN-1",
        "account_type": "retail",
        "risk_profile": "feeder",
    },
    {
        "account_id": "ACC-MID-SG-MULE",
        "name": "Harbour Relay Pte",
        "country": "SG",
        "opened_date": "2026-08-28",
        "occupation": "logistics",
        "stated_income_usd": 12000,
        "kyc_tier": "basic",
        "fraud_label": "mule_pass_through",
        "bank_id": "BANK_SG",
        "customer_id": "CUS-MID-SG-1",
        "account_type": "sme",
        "risk_profile": "mule",
    },
    {
        "account_id": "ACC-MID-PH-EXIT",
        "name": "Cebu Rails Collections",
        "country": "PH",
        "opened_date": "2026-03-04",
        "occupation": "collections",
        "stated_income_usd": 9000,
        "kyc_tier": "standard",
        "fraud_label": "mule_pass_through",
        "bank_id": "BANK_PH",
        "customer_id": "CUS-MID-PH-1",
        "account_type": "sme",
        "risk_profile": "sink",
    },
]

# Only the hops the middle bank can see. No Bank D / off-ramp rows.
TXNS = [
    ("CW-MID-01", "ACC-MID-IN-FEED", "ACC-MID-SG-MULE", 9200, "IN->SG", "BANK_IN", "BANK_SG", "vendor settlement", "business income", "mule_pass_through", 0),
    ("CW-MID-02", "ACC-MID-SG-MULE", "ACC-MID-PH-EXIT", 9050, "SG->PH", "BANK_SG", "BANK_PH", "correspondent cover", "business income", "mule_pass_through", 18),
]


def _base_ts() -> datetime:
    return datetime(2026, 9, 12, 8, 40, tzinfo=timezone.utc)


def seed_middle_bank() -> dict:
    init_schema()
    con = connect()
    existing = con.execute(
        "SELECT txn_id FROM flagged_transactions WHERE txn_id=?",
        (HERO_TXN_ID,),
    ).fetchone()
    if existing:
        con.close()
        return describe_middle_bank()
    now = utc_now()
    upsert(con, "devices", "device_id", {
        "device_id": DEVICE_ID,
        "fingerprint": "mid-bank-chrome-sg",
        "first_seen": "2026-08-28T04:00:00+00:00",
        "os": "Windows 11",
        "last_seen": now,
        "country": "SG",
    })
    for acc in ACCOUNTS:
        upsert(con, "accounts", "account_id", acc)
        upsert(con, "account_devices", ("account_id", "device_id"), {
            "account_id": acc["account_id"],
            "device_id": DEVICE_ID,
            "linked_at": acc["opened_date"],
        })
    for row in TXNS:
        txn_id, sender, receiver, amount, corridor, origin_bank, dest_bank, purpose, sof, scenario, offset = row
        ts = (_base_ts() + timedelta(minutes=offset)).isoformat()
        origin, dest = corridor.split("->")
        upsert(con, "transactions", "txn_id", {
            "txn_id": txn_id,
            "sender_id": sender,
            "receiver_id": receiver,
            "amount": amount,
            "currency": "USD",
            "corridor": corridor,
            "ts": ts,
            "device_id": DEVICE_ID,
            "session_id": f"S-{txn_id}",
            "beneficiary_id": None,
            "purpose": purpose,
            "source_of_funds": sof,
            "fraud_scenario": scenario,
            "origin_country": origin,
            "destination_country": dest,
            "origin_bank_id": origin_bank,
            "destination_bank_id": dest_bank,
            "channel": "swift_gpi",
            "risk_score": 90 if txn_id == HERO_TXN_ID else 82,
            "risk_tier": "CRITICAL" if txn_id == HERO_TXN_ID else "HIGH",
            "status": "posted",
        })
        upsert(con, "flagged_transactions", "txn_id", {
            "txn_id": txn_id,
            "sender_id": sender,
            "receiver_id": receiver,
            "amount": amount,
            "corridor": corridor,
            "ts": ts,
            "risk_score": 91 if txn_id == HERO_TXN_ID else 80,
            "primary_pattern": scenario,
            "fraud_scenario": scenario,
            "currency": "USD",
            "purpose": purpose,
            "source_of_funds": sof,
            "risk_tier": "CRITICAL" if txn_id == HERO_TXN_ID else "HIGH",
            "network_id": NETWORK_ID,
            "workflow_state": "analyst_review" if txn_id == HERO_TXN_ID else "open",
            "showcase": SHOWCASE_FLAG,
        })
        upsert(con, "investigation_queue", "queue_id", {
            "queue_id": f"Q-{txn_id}",
            "txn_id": txn_id,
            "network_id": NETWORK_ID,
            "risk_tier": "CRITICAL" if txn_id == HERO_TXN_ID else "HIGH",
            "status": "QUEUED",
            "created_at": ts,
            "updated_at": now,
        })
    upsert(con, "risk_scores", "account_id", {
        "account_id": "ACC-MID-SG-MULE",
        "risk_score": 91,
        "fan_in_count": 3,
        "fan_out_count": 1,
        "pass_through_ratio": 0.98,
        "avg_hold_time_minutes": 18,
        "shared_device_count": 1,
        "shared_beneficiary_count": 0,
        "multi_hop_chain_depth": 2,
        "account_age_days": 16,
        "corridor_velocity_score": 84,
        "behavioral_risk": 70,
        "primary_pattern": "mule_pass_through",
        "pattern_scores": '{"mule_pass_through":91,"multi_hop_chain":74}',
    })
    con.commit()
    con.close()
    return describe_middle_bank()


def describe_middle_bank() -> dict:
    return {
        "campaign_id": "MIDDLE-BANK",
        "title": "Middle-bank partial network",
        "hero_txn_id": HERO_TXN_ID,
        "home_institution": "BANK_SG",
        "observed_path": "BANK_IN → BANK_SG → BANK_PH",
        "unknown": ["BANK_HK / Bank D", "final off-ramp"],
        "story": (
            "Corridor Watch is the middle bank. Upstream and internal hops are visible. "
            "Downstream beyond BANK_PH is unresolved until authorized intelligence arrives."
        ),
        "visibility_note": "PARTIAL NETWORK OBSERVED — upstream partial, internal full, downstream partial.",
    }
