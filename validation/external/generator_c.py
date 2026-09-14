"""Distribution C — independent of data_gen and generator B.

Frozen seed 23. Do not retune graph_features.py against this seed.
GBP/JPY, 2023 clock, bipartite+mesh+funnel topologies, unseen fraud names.
# ponytail: public-dataset adapter if AMLSim lands; this is the one-shot holdout.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

SEED = 23
NOW = datetime(2026, 9, 1)
POSITIVE_C = {"layering_cascade", "dormant_wake", "funnel_exit", "mirror_peel"}
KNOWN_A_B = {
    "mule_pass_through", "split_transaction_laundering", "shared_device_ring",
    "synthetic_identity", "multi_hop_chain", "circular_pass", "burst_smurf",
}


def build(*, seed: int = SEED) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    t0 = datetime(2023, 11, 12, 7, 40, 0)
    accounts: list[dict] = []
    txns: list[dict] = []

    def acc(prefix: str, country: str, age: int) -> dict:
        row = {
            "account_id": f"C-{prefix}-{len(accounts):04d}",
            "name": f"{prefix} {len(accounts)}",
            "country": country,
            "opened_date": (NOW - timedelta(days=age)).date().isoformat(),
            "occupation": "ops",
            "stated_income_usd": 62000,
            "kyc_tier": "standard",
            "fraud_label": 0,
            "bank_id": f"BANK_{country}",
            "account_age_days": age,
        }
        accounts.append(row)
        return row

    def wire(a, b, amount, corridor, ts, scenario, currency="GBP", purpose="settlement"):
        txns.append({
            "txn_id": f"C-{len(txns):04d}-{scenario[:3].upper()}",
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

    buyers = [acc("BUY", "GB", rng.randint(400, 2200)) for _ in range(8)]
    sellers = [acc("SEL", "GB", rng.randint(500, 2400)) for _ in range(6)]
    for i, buy in enumerate(buyers):
        for sel in rng.sample(sellers, k=2):
            wire(buy, sel, rng.lognormvariate(4.2, 0.35), "GB->GB",
                 t0 + timedelta(hours=i * 3 + rng.randint(0, 2)), "normal", purpose="market")

    for i in range(5):
        home, away = acc("FAM", "GB", rng.randint(600, 1800)), acc("KIN", "NG", rng.randint(500, 1600))
        wire(home, away, rng.uniform(400, 1800), "GB->NG", t0 + timedelta(days=i * 4), "normal", purpose="remit")
        wire(away, home, rng.uniform(350, 1600), "NG->GB", t0 + timedelta(days=i * 4, hours=18), "normal", purpose="remit")

    for i in range(4):
        a, b = acc("FXA", "GB", rng.randint(800, 2000)), acc("FXB", "JP", rng.randint(700, 1900))
        amt = rng.uniform(48000, 52000)
        wire(a, b, amt, "GB->JP", t0 + timedelta(days=20 + i), "normal", purpose="hedge")
        wire(b, a, amt * rng.uniform(0.97, 1.01), "JP->GB", t0 + timedelta(days=21 + i), "normal", currency="JPY", purpose="hedge")

    hub = acc("YENPAY", "JP", 2100)
    for i in range(10):
        leaf = acc("STAFF", "JP", rng.randint(700, 1900))
        wire(hub, leaf, rng.uniform(180000, 240000), "JP->JP", t0 + timedelta(days=i), "normal", currency="JPY", purpose="payroll")

    for i in range(12):
        a, b = rng.choice(buyers + sellers), rng.choice(buyers + sellers)
        if a is b:
            continue
        wire(a, b, rng.uniform(8, 90), "GB->GB", t0 + timedelta(hours=rng.randint(1, 200)), "normal", purpose="noise")

    uni = acc("UNI", "GB", 3200)
    for i in range(8):
        stu = acc("STU", "GB", rng.randint(200, 800))
        wire(stu, uni, rng.uniform(9000, 12000), "GB->GB", t0 + timedelta(weeks=i), "ambiguous_tuition", purpose="tuition")

    charity = acc("GIFT", "GB", 1900)
    for i in range(10):
        donor = acc("DON", "GB", rng.randint(400, 2000))
        wire(donor, charity, rng.uniform(15, 90), "GB->GB", t0 + timedelta(days=i * 1.4), "ambiguous_charity", purpose="gift")

    hops = [acc("LAY", "GB", rng.randint(3, 9)) for _ in range(5)]
    amts = [14000, 11000, 9000, 7000, 5000]
    for i in range(4):
        if i == 2:
            continue
        wire(hops[i], hops[i + 1], amts[i], "GB->IE", t0 + timedelta(minutes=i * 40), "layering_cascade", purpose="layer")
    ext = acc("EXT", "IE", 12)
    wire(hops[-1], ext, 4200, "IE->??", t0 + timedelta(hours=4), "layering_cascade", purpose="offbook")

    sleeper = acc("SLEEP", "GB", 2200)
    feeder = acc("WAKE", "LU", 6)
    wire(feeder, sleeper, 45000, "LU->GB", t0 + timedelta(days=30), "dormant_wake", purpose="inject")
    for i in range(6):
        sink = acc("SINK", "GB", rng.randint(4, 14))
        wire(sleeper, sink, rng.uniform(6800, 8200), "GB->GB", t0 + timedelta(days=30, minutes=20 + i * 18), "dormant_wake", purpose="peel")

    funnel = acc("FUN", "GB", 40)
    for i in range(9):
        src = acc("IN", "FR", rng.randint(8, 25))
        wire(src, funnel, rng.uniform(600, 900), "FR->GB", t0 + timedelta(hours=i * 5), "funnel_exit", purpose="drip")
    exit_a = acc("OUT", "GB", 11)
    wire(funnel, exit_a, 7100, "GB->GB", t0 + timedelta(days=2, hours=4), "funnel_exit", purpose="exit")

    a = acc("MIR", "GB", 5)
    b = acc("MIRR", "GB", 6)
    for i in range(3):
        if i % 2 == 0:
            wire(a, b, 12000, "GB->GB", t0 + timedelta(days=40, minutes=i * 25), "mirror_peel", purpose="swap")
        else:
            wire(b, a, 11950, "GB->GB", t0 + timedelta(days=40, minutes=i * 25), "mirror_peel", purpose="swap")
    for i in range(4):
        cash = acc("CASH", "GB", rng.randint(2, 10))
        wire(b, cash, rng.uniform(2800, 3100), "GB->GB", t0 + timedelta(days=40, hours=3, minutes=i * 12), "mirror_peel", purpose="cashout")

    return accounts, txns
