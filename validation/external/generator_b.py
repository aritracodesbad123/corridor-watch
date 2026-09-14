"""Distribution B — different assumptions than data_gen.py.

# ponytail: public-dataset adapter if AMLSim/Elliptic/PaySim lands.
EUR, star+cycle graphs, burst clocks, fraud names the A generator never emits.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

SEED = 7
POSITIVE_B = {"circular_pass", "burst_smurf"}


def build(n_normal: int = 80, n_circle: int = 12, n_smurf: int = 16) -> tuple[list[dict], list[dict]]:
    rng = random.Random(SEED)
    t0 = datetime(2024, 6, 1, 9, 0, 0)
    accounts: list[dict] = []
    txns: list[dict] = []

    def acc(prefix: str, country: str, age: int) -> dict:
        row = {
            "account_id": f"{prefix}-{len(accounts):04d}",
            "name": f"{prefix} {len(accounts)}",
            "country": country,
            "opened_date": "2020-01-01",
            "occupation": "ops",
            "stated_income_usd": 50000,
            "kyc_tier": "standard",
            "fraud_label": 0,
            "bank_id": f"BANK_{country}",
            "account_age_days": age,
        }
        accounts.append(row)
        return row

    hub = acc("HUB", "DE", 1800)
    for i in range(n_normal):
        leaf = acc("PAY", "DE", rng.randint(400, 2500))
        txns.append(_txn(hub["account_id"], leaf["account_id"], rng.uniform(80, 420), "DE->DE", t0 + timedelta(minutes=i * 7), "normal"))

    ring = [acc("R", "NL", rng.randint(20, 90)) for _ in range(6)]
    for i in range(n_circle):
        a, b = ring[i % 6], ring[(i + 1) % 6]
        txns.append(_txn(a["account_id"], b["account_id"], 9700 + i, "NL->NL", t0 + timedelta(minutes=i), "circular_pass"))

    collector = acc("SMURF", "FR", 4)
    for i in range(n_smurf):
        src = acc("IN", "BE", rng.randint(2, 9))
        txns.append(_txn(src["account_id"], collector["account_id"], 990, "BE->FR", t0 + timedelta(seconds=i * 40), "burst_smurf"))
    return accounts, txns


def _txn(sender, receiver, amount, corridor, ts, scenario) -> dict:
    return {
        "txn_id": f"B-{scenario[:3].upper()}-{sender[-4:]}-{receiver[-4:]}-{int(amount)}",
        "sender_id": sender,
        "receiver_id": receiver,
        "amount": round(float(amount), 2),
        "currency": "EUR",
        "corridor": corridor,
        "ts": ts.isoformat(),
        "device_id": None,
        "session_id": None,
        "beneficiary_id": None,
        "purpose": "invoice",
        "source_of_funds": "operating",
        "fraud_scenario": scenario,
    }


def write_db(accounts: list[dict], txns: list[dict]) -> None:
    from db import connect, init_schema
    init_schema()
    con = connect()
    con.executemany(
        "INSERT INTO accounts (account_id,name,country,opened_date,occupation,"
        "stated_income_usd,kyc_tier,fraud_label) VALUES (?,?,?,?,?,?,?,?)",
        [(a["account_id"], a["name"], a["country"], a["opened_date"], a["occupation"],
          a["stated_income_usd"], a["kyc_tier"], a["fraud_label"]) for a in accounts],
    )
    con.executemany(
        "INSERT INTO transactions (txn_id,sender_id,receiver_id,amount,currency,corridor,ts,"
        "device_id,session_id,beneficiary_id,purpose,source_of_funds,fraud_scenario) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(t["txn_id"], t["sender_id"], t["receiver_id"], t["amount"], t["currency"], t["corridor"],
          t["ts"], t["device_id"], t["session_id"], t["beneficiary_id"], t["purpose"],
          t["source_of_funds"], t["fraud_scenario"]) for t in txns],
    )
    con.commit()
    con.close()
