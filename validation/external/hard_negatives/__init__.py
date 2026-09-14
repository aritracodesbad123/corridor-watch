"""Legitimate high-complexity networks and fraud twins. Hidden labels via fraud_scenario (eval-only)."""
from __future__ import annotations

import random
from datetime import datetime, timedelta

SEED = 19
POSITIVE = {
    "mule_pass_through", "split_transaction_laundering", "shared_device_ring",
    "burst_smurf", "circular_pass",
}


def build(*, seed: int = SEED) -> tuple[list[dict], list[dict], dict]:
    rng = random.Random(seed)
    t0 = datetime(2025, 3, 1, 8, 0, 0)
    accounts: list[dict] = []
    txns: list[dict] = []
    roles: dict[str, dict] = {}

    def acc(prefix, country, age, **extra):
        row = {
            "account_id": f"{prefix}-{len(accounts):04d}",
            "name": f"{prefix} {len(accounts)}",
            "country": country,
            "opened_date": "2018-01-01" if age > 365 else "2026-08-01",
            "occupation": extra.get("occupation", "ops"),
            "stated_income_usd": extra.get("income", 80000),
            "kyc_tier": "standard",
            "fraud_label": 0,
            "bank_id": f"BANK_{country}",
            "account_age_days": age,
        }
        accounts.append(row)
        return row

    def wire(a, b, amount, corridor, ts, scenario, device=None):
        txns.append({
            "txn_id": f"HN-{len(txns):04d}-{scenario[:3]}",
            "sender_id": a["account_id"],
            "receiver_id": b["account_id"],
            "amount": round(float(amount), 2),
            "currency": "USD",
            "corridor": corridor,
            "ts": ts.isoformat(),
            "device_id": device,
            "session_id": None,
            "beneficiary_id": None,
            "purpose": scenario,
            "source_of_funds": "operating",
            "fraud_scenario": scenario,
        })

    def star(name, hub_age, leaf_n, amount, corridor, scenario, leaf_age, inbound=False):
        hub = acc(name, corridor.split("->")[0], hub_age)
        leaves = [acc(f"{name}L", corridor.split("->")[-1], leaf_age) for _ in range(leaf_n)]
        roles[hub["account_id"]] = {"role": "anchor", "typology": name, "label": scenario}
        path = [hub["account_id"]]
        for i, leaf in enumerate(leaves):
            roles[leaf["account_id"]] = {"role": "leaf", "typology": name, "label": scenario}
            ts = t0 + timedelta(minutes=i * 12)
            if inbound:
                wire(leaf, hub, amount, corridor, ts, scenario)
            else:
                wire(hub, leaf, amount, corridor, ts, scenario)
            path = [hub["account_id"], leaf["account_id"]]
        roles[hub["account_id"]]["path"] = path
        roles[hub["account_id"]]["critical"] = True
        return hub, leaves

    # 10 legitimate archetypes (source-only or old accounts)
    star("PAYROLL", 2000, 6, 3100, "SG->SG", "normal", 800)
    star("TREASURY", 2500, 5, 18000, "SG->SG", "normal", 900)
    star("MARKET", 1200, 8, 55, "US->US", "normal", 400)
    star("FAMILY", 900, 3, 700, "IN->SG", "normal", 600)
    star("CHARITY", 1800, 5, 250, "UK->UK", "normal", 500)
    star("MERCHANT", 1500, 6, 120, "SG->SG", "normal", 700)
    star("REMIT", 1100, 4, 900, "PH->SG", "normal", 650)
    star("SUBS", 1300, 7, 15, "US->US", "normal", 300)
    star("SHARED", 1600, 4, 2200, "SG->MY", "normal", 1000)
    hh = acc("HOUSE", "IN", 1400)
    kin = [acc("KIN", "IN", 700) for _ in range(3)]
    roles[hh["account_id"]] = {"role": "anchor", "typology": "household", "label": "normal", "critical": True}
    for i, k in enumerate(kin):
        roles[k["account_id"]] = {"role": "leaf", "typology": "household", "label": "normal"}
        wire(hh, k, 400 + i, "IN->IN", t0 + timedelta(days=i), "normal", device="DEV-HOUSE")

    # Fraud twins: inbound fan-in / young mule / pass-through
    star("MULEHUB", 4, 6, 980, "BE->FR", "burst_smurf", 3, inbound=True)
    star("SMURFSINK", 6, 8, 990, "NL->NL", "split_transaction_laundering", 5, inbound=True)
    mule = acc("MULE", "PH", 3)
    cash = acc("CASHOUT", "SG", 5)
    roles[mule["account_id"]] = {"role": "anchor", "typology": "mule_pass_through", "label": "mule_pass_through", "critical": True,
                                 "path": [mule["account_id"], cash["account_id"]]}
    roles[cash["account_id"]] = {"role": "critical", "typology": "mule_pass_through", "label": "mule_pass_through"}
    feeder = acc("FEED", "PH", 2)
    wire(feeder, mule, 12000, "PH->PH", t0, "mule_pass_through")
    wire(mule, cash, 11800, "PH->SG", t0 + timedelta(minutes=25), "mule_pass_through")
    ring = [acc("RING", "ID", rng.randint(4, 12)) for _ in range(4)]
    for i, node in enumerate(ring):
        roles[node["account_id"]] = {"role": "critical" if i == 0 else "leaf", "typology": "circular_pass",
                                     "label": "circular_pass"}
        nxt = ring[(i + 1) % 4]
        wire(node, nxt, 9700, "ID->ID", t0 + timedelta(minutes=i), "circular_pass")
    roles[ring[0]["account_id"]]["role"] = "anchor"
    roles[ring[0]["account_id"]]["critical"] = True
    roles[ring[0]["account_id"]]["path"] = [r["account_id"] for r in ring] + [ring[0]["account_id"]]
    return accounts, txns, roles
