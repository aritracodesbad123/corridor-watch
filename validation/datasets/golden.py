"""100-case AI/deterministic investigation set. Mix of kinds, seed 42."""
from __future__ import annotations

import json
from pathlib import Path

KINDS = (
    ("mule", 20, {"amount": 15000, "account_age_days": 2, "fraud_scenario": "mule_pass_through"}, "hold_payment"),
    ("hop", 20, {"amount": 18000, "account_age_days": 3, "fraud_scenario": "multi_hop_chain"}, "hold_payment"),
    ("normal", 20, {"amount": 400, "account_age_days": 900, "fraud_scenario": "normal"}, "clear"),
    ("hardneg", 15, {"amount": 12000, "account_age_days": 800, "fraud_scenario": "normal"}, "clear"),
    ("hybrid", 10, {"amount": 9900, "account_age_days": 5, "fraud_scenario": "mule_pass_through"}, "hold_payment"),
    ("partial", 10, {"amount": 8000, "account_age_days": 10, "fraud_scenario": "split_transaction_laundering"}, "hold_payment"),
    ("adversarial", 5, {"amount": 7000, "account_age_days": 6, "fraud_scenario": "shared_device_ring"}, "hold_payment"),
)


def cases() -> list[dict]:
    rows = []
    n = 0
    for kind, count, base, expected in KINDS:
        for i in range(count):
            n += 1
            txn_id = f"GOLD-{kind.upper()}-{i+1:03d}"
            rows.append({
                "txn_id": txn_id,
                "source_event_id": f"E-{txn_id}",
                "kind": kind,
                "expected_disposition": expected,
                "evidence_ids": ["E-TXN"],
                **base,
                "amount": base["amount"] + i,
            })
    return rows


def write_jsonl(path: Path | None = None) -> Path:
    path = path or Path(__file__).with_name("golden_investigations.jsonl")
    path.write_text("".join(json.dumps(r) + "\n" for r in cases()))
    return path
