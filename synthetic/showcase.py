"""Lotus Ring — one cross-bank suspicious network for the live console."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db import connect, init_schema, upsert
from pubsub.schemas import utc_now

NETWORK_ID = "NET-LOTUS-RING"
HERO_TXN_ID = "CW-LOTUS-04"
DEVICE_ID = "D-LOTUS"
BENEFICIARY_ID = "BN-LOTUS-SINK"
SHOWCASE_FLAG = "lotus_ring"

ACCOUNTS = [
    {
        "account_id": "ACC-LOTUS-IN-1",
        "name": "R. Menon Payroll",
        "country": "IN",
        "opened_date": "2025-11-02",
        "occupation": "warehouse supervisor",
        "stated_income_usd": 7800,
        "kyc_tier": "standard",
        "fraud_label": "multi_hop_chain",
        "bank_id": "BANK_IN",
        "customer_id": "CUS-LOTUS-IN-1",
        "account_type": "retail",
        "risk_profile": "payroll_source",
    },
    {
        "account_id": "ACC-LOTUS-IN-2",
        "name": "K. Iyer Disbursements",
        "country": "IN",
        "opened_date": "2025-12-18",
        "occupation": "contractor",
        "stated_income_usd": 6200,
        "kyc_tier": "standard",
        "fraud_label": "split_transaction_laundering",
        "bank_id": "BANK_IN",
        "customer_id": "CUS-LOTUS-IN-2",
        "account_type": "retail",
        "risk_profile": "feeder",
    },
    {
        "account_id": "ACC-LOTUS-IN-3",
        "name": "S. Rao Trade Desk",
        "country": "IN",
        "opened_date": "2026-01-09",
        "occupation": "import clerk",
        "stated_income_usd": 5400,
        "kyc_tier": "standard",
        "fraud_label": "split_transaction_laundering",
        "bank_id": "BANK_IN",
        "customer_id": "CUS-LOTUS-IN-3",
        "account_type": "retail",
        "risk_profile": "feeder",
    },
    {
        "account_id": "ACC-LOTUS-SG-MULE",
        "name": "Apex Harbour Logistics",
        "country": "SG",
        "opened_date": "2026-08-21",
        "occupation": "logistics",
        "stated_income_usd": 18000,
        "kyc_tier": "enhanced",
        "fraud_label": "mule_pass_through",
        "bank_id": "BANK_SG",
        "customer_id": "CUS-LOTUS-SG-1",
        "account_type": "sme",
        "risk_profile": "mule",
    },
    {
        "account_id": "ACC-LOTUS-SG-CTRL",
        "name": "Harbour Desk Ops",
        "country": "SG",
        "opened_date": "2026-08-22",
        "occupation": "operations",
        "stated_income_usd": 16000,
        "kyc_tier": "standard",
        "fraud_label": "shared_device_ring",
        "bank_id": "BANK_SG",
        "customer_id": "CUS-LOTUS-SG-2",
        "account_type": "sme",
        "risk_profile": "controller",
    },
    {
        "account_id": "ACC-LOTUS-AE-HOP",
        "name": "Mirage Clearing FZE",
        "country": "AE",
        "opened_date": "2026-07-04",
        "occupation": "trade finance",
        "stated_income_usd": 42000,
        "kyc_tier": "enhanced",
        "fraud_label": "multi_hop_chain",
        "bank_id": "BANK_AE",
        "customer_id": "CUS-LOTUS-AE-1",
        "account_type": "corporate",
        "risk_profile": "hop",
    },
    {
        "account_id": "ACC-LOTUS-PH-SINK",
        "name": "Pacific Rim Settlements",
        "country": "PH",
        "opened_date": "2026-06-11",
        "occupation": "settlement agent",
        "stated_income_usd": 24000,
        "kyc_tier": "standard",
        "fraud_label": "multi_hop_chain",
        "bank_id": "BANK_PH",
        "customer_id": "CUS-LOTUS-PH-1",
        "account_type": "corporate",
        "risk_profile": "sink",
    },
]

TXNS = [
    ("CW-LOTUS-01", "ACC-LOTUS-IN-1", "ACC-LOTUS-SG-MULE", 2840.0, "IN->SG", "BANK_IN", "BANK_SG", "salary", "payroll credit", "split_transaction_laundering", 0),
    ("CW-LOTUS-02", "ACC-LOTUS-IN-2", "ACC-LOTUS-SG-MULE", 2715.0, "IN->SG", "BANK_IN", "BANK_SG", "invoice", "contract proceeds", "split_transaction_laundering", 45),
    ("CW-LOTUS-03", "ACC-LOTUS-IN-3", "ACC-LOTUS-SG-MULE", 2960.0, "IN->SG", "BANK_IN", "BANK_SG", "goods", "trade receivable", "split_transaction_laundering", 80),
    ("CW-LOTUS-04", "ACC-LOTUS-SG-MULE", "ACC-LOTUS-AE-HOP", 8200.0, "SG->AE", "BANK_SG", "BANK_AE", "intercompany", "working capital", "mule_pass_through", 140),
    ("CW-LOTUS-05", "ACC-LOTUS-SG-CTRL", "ACC-LOTUS-AE-HOP", 1900.0, "SG->AE", "BANK_SG", "BANK_AE", "ops float", "internal transfer", "shared_device_ring", 155),
    ("CW-LOTUS-06", "ACC-LOTUS-AE-HOP", "ACC-LOTUS-PH-SINK", 8050.0, "AE->PH", "BANK_AE", "BANK_PH", "settlement", "correspondent cover", "multi_hop_chain", 210),
    ("CW-LOTUS-07", "ACC-LOTUS-IN-1", "ACC-LOTUS-SG-MULE", 1880.0, "IN->SG", "BANK_IN", "BANK_SG", "bonus", "payroll credit", "split_transaction_laundering", 260),
]


def _base_ts() -> datetime:
    return datetime(2026, 9, 11, 6, 15, tzinfo=timezone.utc)


def seed_showcase() -> dict:
    """Idempotent seed of the Lotus Ring campaign."""
    init_schema()
    con = connect()
    existing = con.execute(
        "SELECT txn_id FROM flagged_transactions WHERE txn_id=?",
        (HERO_TXN_ID,),
    ).fetchone()
    if existing:
        con.close()
        return describe_showcase()
    now = utc_now()
    upsert(con, "devices", "device_id", {
        "device_id": DEVICE_ID,
        "fingerprint": "lotus-shared-chrome-sg",
        "first_seen": "2026-08-21T02:11:00+00:00",
        "os": "Windows 11",
        "last_seen": now,
        "country": "SG",
    })
    upsert(con, "beneficiaries", "beneficiary_id", {
        "beneficiary_id": BENEFICIARY_ID,
        "name": "Pacific Rim Settlements",
        "country": "PH",
        "bank_hint": "BANK_PH",
        "bank_id": "BANK_PH",
        "created_at": now,
    })
    for acc in ACCOUNTS:
        upsert(con, "accounts", "account_id", acc)
        upsert(con, "account_devices", ("account_id", "device_id"), {
            "account_id": acc["account_id"],
            "device_id": DEVICE_ID,
            "linked_at": acc["opened_date"],
        })
        upsert(con, "account_beneficiaries", ("account_id", "beneficiary_id"), {
            "account_id": acc["account_id"],
            "beneficiary_id": BENEFICIARY_ID,
            "added_at": acc["opened_date"],
        })

    seeded = []
    for row in TXNS:
        txn_id, sender, receiver, amount, corridor, origin_bank, dest_bank, purpose, sof, scenario, offset = row
        if amount <= 0:
            continue
        ts = (_base_ts() + timedelta(minutes=offset)).isoformat()
        origin, dest = corridor.split("->")
        session_id = f"S-{txn_id}"
        upsert(con, "sessions", "session_id", {
            "session_id": session_id,
            "account_id": sender,
            "device_id": DEVICE_ID,
            "started_at": ts,
            "typing_deviation": 0.81,
            "navigation_velocity": 2.4,
            "bot_likelihood": 0.62,
            "copy_paste_risk": 0.71,
            "geo_mismatch": 1,
        })
        upsert(con, "transactions", "txn_id", {
            "txn_id": txn_id,
            "sender_id": sender,
            "receiver_id": receiver,
            "amount": amount,
            "currency": "USD",
            "corridor": corridor,
            "ts": ts,
            "device_id": DEVICE_ID,
            "session_id": session_id,
            "beneficiary_id": BENEFICIARY_ID,
            "purpose": purpose,
            "source_of_funds": sof,
            "fraud_scenario": scenario,
            "origin_country": origin,
            "destination_country": dest,
            "origin_bank_id": origin_bank,
            "destination_bank_id": dest_bank,
            "channel": "swift_gpi",
            "risk_score": 88 if txn_id == HERO_TXN_ID else 76,
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
            "risk_score": 91 if txn_id == HERO_TXN_ID else 78,
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
            "status": "pending",
            "created_at": ts,
            "updated_at": now,
        })
        seeded.append(txn_id)

    for account_id, score, pattern, age, ptr, hold, fan_in in (
        ("ACC-LOTUS-SG-MULE", 91, "mule_pass_through", 23, 0.96, 28, 4),
        ("ACC-LOTUS-SG-CTRL", 74, "shared_device_ring", 22, 0.88, 40, 1),
        ("ACC-LOTUS-AE-HOP", 86, "multi_hop_chain", 71, 0.94, 55, 2),
        ("ACC-LOTUS-PH-SINK", 80, "multi_hop_chain", 94, 0.11, 720, 2),
        ("ACC-LOTUS-IN-1", 61, "split_transaction_laundering", 315, 0.22, 1440, 0),
        ("ACC-LOTUS-IN-2", 63, "split_transaction_laundering", 269, 0.19, 1440, 0),
        ("ACC-LOTUS-IN-3", 64, "split_transaction_laundering", 247, 0.21, 1440, 0),
    ):
        upsert(con, "risk_scores", "account_id", {
            "account_id": account_id,
            "risk_score": score,
            "fan_in_count": fan_in,
            "fan_out_count": 2 if account_id.endswith("MULE") else 1,
            "pass_through_ratio": ptr,
            "avg_hold_time_minutes": hold,
            "shared_device_count": 2,
            "shared_beneficiary_count": 1,
            "multi_hop_chain_depth": 3,
            "account_age_days": age,
            "corridor_velocity_score": 81,
            "behavioral_risk": 72,
            "primary_pattern": pattern,
            "pattern_scores": (
                '{"mule_pass_through":88,"split_transaction_laundering":76,'
                '"shared_device_ring":70,"multi_hop_chain":84}'
            ),
        })

    con.commit()
    con.close()
    return describe_showcase()


def describe_showcase() -> dict:
    return {
        "campaign_id": "LOTUS-RING",
        "title": "Lotus Ring — India payroll to Philippines sink",
        "hero_txn_id": HERO_TXN_ID,
        "network_id": NETWORK_ID,
        "institutions": [
            {"bank_id": "BANK_IN", "name": "Deccan Synthetic Bank", "role": "origin feeders"},
            {"bank_id": "BANK_SG", "name": "Lion City Synthetic Bank", "role": "mule / shared device"},
            {"bank_id": "BANK_AE", "name": "Oasis Synthetic Bank", "role": "clearing hop"},
            {"bank_id": "BANK_PH", "name": "Archipelago Synthetic Bank", "role": "exit sink"},
        ],
        "corridors": ["IN->SG", "SG->AE", "AE->PH"],
        "txn_ids": [row[0] for row in TXNS if row[3] > 0],
        "shared_device": DEVICE_ID,
        "story": (
            "Three India-origin credits stay under a three-thousand threshold, land on a "
            "twenty-three-day Singapore mule, and leave the same hardware fingerprint as a "
            "second Lion City control account. The mule forwards almost the full balance to "
            "an Emirates clearing hop within two hours; the hop exits to a Philippines sink "
            "on the same beneficiary. Seven wires, four banks, one network investigation."
        ),
    }
