"""Distribution F — last freeze. Not Dist E.

Frozen seed 47. Freeze graph_features before scoring. Do not retune on this seed.
INR/SGD, 2020 clock, port-warehouse-retailer. FAMILY is eval-only.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

SEED = 47
NOW = datetime(2026, 9, 1)
POSITIVE_F = {"dock_smurf", "berth_skip", "quay_wake", "trade_overbill"}
# Eval-only. Detector never sees these names. Unmapped keys omitted on purpose.
FAMILY = {
    "dock_smurf": "split_transaction_laundering",
    "berth_skip": "multi_hop_chain",
    "quay_wake": "mule_pass_through",
}
KNOWN_A_TO_E = {
    "mule_pass_through", "split_transaction_laundering", "shared_device_ring",
    "synthetic_identity", "multi_hop_chain", "circular_pass", "burst_smurf",
    "layering_cascade", "dormant_wake", "funnel_exit", "mirror_peel",
    "invoice_loop", "nested_shell", "drain_wake", "burst_sink",
    "round_trip_peel", "skip_hop", "dormant_drain", "pulse_smurf",
}


def build(*, seed: int = SEED) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    t0 = datetime(2020, 2, 11, 8, 5, 0)
    accounts: list[dict] = []
    txns: list[dict] = []

    def acc(prefix: str, country: str, age: int) -> dict:
        row = {
            "account_id": f"F-{prefix}-{len(accounts):04d}",
            "name": f"{prefix} {len(accounts)}",
            "country": country,
            "opened_date": (NOW - timedelta(days=age)).date().isoformat(),
            "occupation": "ops",
            "stated_income_usd": 58000,
            "kyc_tier": "standard",
            "fraud_label": 0,
            "bank_id": f"BANK_{country}",
            "account_age_days": age,
        }
        accounts.append(row)
        return row

    def wire(a, b, amount, corridor, ts, scenario, currency="INR", purpose="settlement"):
        txns.append({
            "txn_id": f"F-{len(txns):04d}-{scenario[:3].upper()}",
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

    ports = [acc("PORT", "IN", rng.randint(700, 2200)) for _ in range(5)]
    warehouses = [acc("WH", "IN", rng.randint(800, 2400)) for _ in range(4)]
    shops = [acc("RET", "SG", rng.randint(500, 1900)) for _ in range(5)]
    for i, port in enumerate(ports):
        wh = warehouses[i % len(warehouses)]
        wire(port, wh, rng.uniform(1800, 5400), "IN->IN", t0 + timedelta(days=i * 5), "normal", purpose="cargo")
    for i, wh in enumerate(warehouses):
        shop = shops[i % len(shops)]
        wire(wh, shop, rng.uniform(1200, 4100), "IN->SG", t0 + timedelta(days=3 + i * 5), "normal", currency="SGD", purpose="wholesale")

    co = acc("DIVIN", "IN", 2500)
    for i in range(6):
        sh = acc("HOLD", "IN", rng.randint(400, 1800))
        wire(co, sh, rng.uniform(0.28, 1.2), "IN->IN", t0 + timedelta(days=45 + i), "normal", purpose="dividend")

    for i in range(3):
        a, b = acc("SGA", "SG", rng.randint(600, 1800)), acc("SGB", "IN", rng.randint(500, 1700))
        amt = rng.uniform(11000, 17000)
        wire(a, b, amt, "SG->IN", t0 + timedelta(days=14 + i * 6), "normal", currency="SGD", purpose="trade")
        wire(b, a, amt * rng.uniform(0.96, 1.02), "IN->SG", t0 + timedelta(days=16 + i * 6), "normal", purpose="trade")

    pool = warehouses + shops
    for i in range(14):
        a, b = rng.choice(pool), rng.choice(pool)
        if a is b:
            continue
        wire(a, b, rng.uniform(14, 80), "IN->SG", t0 + timedelta(hours=rng.randint(4, 160)), "normal", currency="SGD", purpose="noise")

    mandir = acc("MANDIR", "IN", 2300)
    for i in range(8):
        d = acc("DON", "IN", rng.randint(300, 1400))
        wire(d, mandir, rng.uniform(20, 90), "IN->IN", t0 + timedelta(days=i * 2.1), "ambiguous_mandir", purpose="gift")

    union = acc("UNION", "SG", 1700)
    for i in range(7):
        m = acc("MEM", "SG", rng.randint(400, 1500))
        wire(m, union, rng.uniform(12, 55), "SG->SG", t0 + timedelta(days=i * 1.8), "ambiguous_union", currency="SGD", purpose="dues")

    sink = acc("DOCK", "IN", 5)
    for i in range(14):
        src = acc("DRIP", "SG", rng.randint(2, 8))
        wire(src, sink, rng.uniform(380, 640), "SG->IN", t0 + timedelta(days=70, seconds=i * 30), "dock_smurf", currency="SGD", purpose="smurf")

    hops = [acc("BERTH", "SG", rng.randint(3, 8)) for _ in range(5)]
    amts = [15000, 11800, 9200, 7000, 4800]
    for i in range(4):
        if i == 2:
            continue
        wire(hops[i], hops[i + 1], amts[i], "SG->SG", t0 + timedelta(days=75, minutes=i * 42), "berth_skip", currency="SGD", purpose="layer")
    ext = acc("OFF", "SG", 10)
    wire(hops[-1], ext, 3900, "SG->??", t0 + timedelta(days=75, hours=4), "berth_skip", currency="SGD", purpose="offbook")

    sleeper = acc("QUAY", "IN", 2000)
    inj = acc("INJ", "SG", 4)
    wire(inj, sleeper, 36000, "SG->IN", t0 + timedelta(days=80), "quay_wake", currency="SGD", purpose="inject")
    for i in range(5):
        out = acc("DRAIN", "IN", rng.randint(3, 10))
        wire(sleeper, out, rng.uniform(6100, 7800), "IN->IN", t0 + timedelta(days=80, minutes=16 + i * 21), "quay_wake", purpose="peel")

    a = acc("BILL", "IN", 6)
    b = acc("BILLB", "SG", 5)
    for i in range(4):
        wire(a, b, 24000 + i * 400, "IN->SG", t0 + timedelta(days=85, minutes=i * 28), "trade_overbill", purpose="invoice")
        wire(b, a, 23800 + i * 350, "SG->IN", t0 + timedelta(days=85, minutes=12 + i * 28), "trade_overbill", currency="SGD", purpose="invoice")

    return accounts, txns
