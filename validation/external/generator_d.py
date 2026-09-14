"""Distribution D — post-fix holdout. Not Dist C.

Frozen seed 37. Freeze graph_features before scoring. Do not retune on this seed.
AUD/CHF, 2022 clock, tripartite supply chain, unseen fraud names.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

SEED = 37
NOW = datetime(2026, 9, 1)
POSITIVE_D = {"invoice_loop", "nested_shell", "drain_wake", "burst_sink"}
KNOWN_A_B_C = {
    "mule_pass_through", "split_transaction_laundering", "shared_device_ring",
    "synthetic_identity", "multi_hop_chain", "circular_pass", "burst_smurf",
    "layering_cascade", "dormant_wake", "funnel_exit", "mirror_peel",
}


def build(*, seed: int = SEED) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    t0 = datetime(2022, 4, 3, 6, 15, 0)
    accounts: list[dict] = []
    txns: list[dict] = []

    def acc(prefix: str, country: str, age: int) -> dict:
        row = {
            "account_id": f"D-{prefix}-{len(accounts):04d}",
            "name": f"{prefix} {len(accounts)}",
            "country": country,
            "opened_date": (NOW - timedelta(days=age)).date().isoformat(),
            "occupation": "ops",
            "stated_income_usd": 71000,
            "kyc_tier": "standard",
            "fraud_label": 0,
            "bank_id": f"BANK_{country}",
            "account_age_days": age,
        }
        accounts.append(row)
        return row

    def wire(a, b, amount, corridor, ts, scenario, currency="AUD", purpose="settlement"):
        txns.append({
            "txn_id": f"D-{len(txns):04d}-{scenario[:3].upper()}",
            "sender_id": a["account_id"],
            "receiver_id": b["account_id"],
            "amount": round(float(amount), 2),
            "currency": currency,
            "corridor": corridor,
            "ts": ts.isoformat(),
            "device_id": None,
            "session_id": None,
            "beneficiary_id": None,
            "purpose": purpose,
            "source_of_funds": "operating",
            "fraud_scenario": scenario,
        })

    farms = [acc("FARM", "AU", rng.randint(800, 2400)) for _ in range(6)]
    mills = [acc("MILL", "AU", rng.randint(900, 2500)) for _ in range(4)]
    shops = [acc("SHOP", "AU", rng.randint(500, 1800)) for _ in range(5)]
    for i, farm in enumerate(farms):
        mill = mills[i % len(mills)]
        wire(farm, mill, rng.uniform(1200, 4800), "AU->AU", t0 + timedelta(days=i * 3), "normal", purpose="harvest")
    for i, mill in enumerate(mills):
        shop = shops[i % len(shops)]
        wire(mill, shop, rng.uniform(900, 3600), "AU->AU", t0 + timedelta(days=2 + i * 3), "normal", purpose="wholesale")

    co = acc("DIVCO", "AU", 2800)
    for i in range(8):
        sh = acc("HOLD", "AU", rng.randint(400, 2000))
        wire(co, sh, rng.uniform(0.42, 1.85), "AU->AU", t0 + timedelta(days=40 + i), "normal", purpose="dividend")

    for i in range(4):
        a, b = acc("CHFA", "CH", rng.randint(700, 1900)), acc("CHFB", "AU", rng.randint(600, 1700))
        amt = rng.uniform(18000, 26000)
        wire(a, b, amt, "CH->AU", t0 + timedelta(days=10 + i * 5), "normal", currency="CHF", purpose="trade")
        wire(b, a, amt * rng.uniform(0.96, 1.02), "AU->CH", t0 + timedelta(days=12 + i * 5), "normal", purpose="trade")

    for i in range(10):
        a, b = rng.choice(mills + shops), rng.choice(mills + shops)
        if a is b:
            continue
        wire(a, b, rng.uniform(12, 110), "AU->AU", t0 + timedelta(hours=rng.randint(2, 180)), "normal", purpose="noise")

    clinic = acc("CLINIC", "AU", 2600)
    for i in range(9):
        p = acc("PAT", "AU", rng.randint(300, 1600))
        wire(p, clinic, rng.uniform(80, 240), "AU->AU", t0 + timedelta(days=i * 2), "ambiguous_clinic", purpose="billing")

    kirk = acc("KIRK", "CH", 2100)
    for i in range(8):
        tither = acc("TITHE", "CH", rng.randint(400, 1800))
        wire(tither, kirk, rng.uniform(20, 75), "CH->CH", t0 + timedelta(days=i * 1.7), "ambiguous_tithe", currency="CHF", purpose="gift")

    loop = [acc("INV", "AU", rng.randint(4, 11)) for _ in range(3)]
    for i, node in enumerate(loop):
        nxt = loop[(i + 1) % 3]
        wire(node, nxt, 22000 + i, "AU->AU", t0 + timedelta(days=50, minutes=i * 35), "invoice_loop", purpose="invoice")

    shells = [acc("SHELL", "CH", rng.randint(3, 8)) for _ in range(5)]
    for i in range(4):
        if i == 2:
            continue
        wire(shells[i], shells[i + 1], 15000 - i * 1800, "CH->CH", t0 + timedelta(days=55, minutes=i * 50), "nested_shell", currency="CHF", purpose="layer")
    ext = acc("OFF", "CH", 9)
    wire(shells[-1], ext, 6100, "CH->??", t0 + timedelta(days=55, hours=5), "nested_shell", currency="CHF", purpose="offbook")

    sleeper = acc("OLD", "AU", 2400)
    inj = acc("INJ", "CH", 5)
    wire(inj, sleeper, 38000, "CH->AU", t0 + timedelta(days=60), "drain_wake", currency="CHF", purpose="inject")
    for i in range(5):
        out = acc("DRAIN", "AU", rng.randint(3, 12))
        wire(sleeper, out, rng.uniform(6200, 7900), "AU->AU", t0 + timedelta(days=60, minutes=15 + i * 20), "drain_wake", purpose="peel")

    sink = acc("SINK", "AU", 5)
    for i in range(14):
        src = acc("DRIP", "AU", rng.randint(2, 9))
        wire(src, sink, rng.uniform(400, 700), "AU->AU", t0 + timedelta(days=70, seconds=i * 28), "burst_sink", purpose="smurf")

    return accounts, txns
