"""Distribution E — post-fix holdout. Not Dist D.

Frozen seed 41. Freeze graph_features before scoring. Do not retune on this seed.
CAD/MXN, 2021 clock, four-stage mine-smelter-trader-yard, unseen fraud names.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

SEED = 41
NOW = datetime(2026, 9, 1)
POSITIVE_E = {"round_trip_peel", "skip_hop", "dormant_drain", "pulse_smurf"}
KNOWN_A_B_C_D = {
    "mule_pass_through", "split_transaction_laundering", "shared_device_ring",
    "synthetic_identity", "multi_hop_chain", "circular_pass", "burst_smurf",
    "layering_cascade", "dormant_wake", "funnel_exit", "mirror_peel",
    "invoice_loop", "nested_shell", "drain_wake", "burst_sink",
}


def build(*, seed: int = SEED) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    t0 = datetime(2021, 6, 8, 9, 20, 0)
    accounts: list[dict] = []
    txns: list[dict] = []

    def acc(prefix: str, country: str, age: int) -> dict:
        row = {
            "account_id": f"E-{prefix}-{len(accounts):04d}",
            "name": f"{prefix} {len(accounts)}",
            "country": country,
            "opened_date": (NOW - timedelta(days=age)).date().isoformat(),
            "occupation": "ops",
            "stated_income_usd": 64000,
            "kyc_tier": "standard",
            "fraud_label": 0,
            "bank_id": f"BANK_{country}",
            "account_age_days": age,
        }
        accounts.append(row)
        return row

    def wire(a, b, amount, corridor, ts, scenario, currency="CAD", purpose="settlement"):
        txns.append({
            "txn_id": f"E-{len(txns):04d}-{scenario[:3].upper()}",
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

    mines = [acc("MINE", "CA", rng.randint(600, 2200)) for _ in range(5)]
    smelters = [acc("SMELT", "CA", rng.randint(800, 2400)) for _ in range(4)]
    traders = [acc("TRADE", "CA", rng.randint(500, 2000)) for _ in range(4)]
    yards = [acc("YARD", "CA", rng.randint(400, 1800)) for _ in range(5)]
    for i, mine in enumerate(mines):
        sm = smelters[i % len(smelters)]
        wire(mine, sm, rng.uniform(2200, 6400), "CA->CA", t0 + timedelta(days=i * 4), "normal", purpose="ore")
    for i, sm in enumerate(smelters):
        tr = traders[i % len(traders)]
        wire(sm, tr, rng.uniform(1800, 5200), "CA->CA", t0 + timedelta(days=2 + i * 4), "normal", purpose="metal")
    for i, tr in enumerate(traders):
        yd = yards[i % len(yards)]
        wire(tr, yd, rng.uniform(1400, 4100), "CA->CA", t0 + timedelta(days=4 + i * 4), "normal", purpose="stock")

    co = acc("ROYCO", "CA", 2600)
    for i in range(6):
        sh = acc("ROY", "CA", rng.randint(400, 1800))
        wire(co, sh, rng.uniform(0.31, 1.4), "CA->CA", t0 + timedelta(days=50 + i), "normal", purpose="royalty")

    for i in range(3):
        a, b = acc("MXA", "MX", rng.randint(700, 1900)), acc("MXB", "CA", rng.randint(600, 1700))
        amt = rng.uniform(14000, 21000)
        wire(a, b, amt, "MX->CA", t0 + timedelta(days=12 + i * 6), "normal", currency="MXN", purpose="trade")
        wire(b, a, amt * rng.uniform(0.95, 1.03), "CA->MX", t0 + timedelta(days=14 + i * 6), "normal", purpose="trade")

    pool = smelters + traders + yards
    for i in range(12):
        a, b = rng.choice(pool), rng.choice(pool)
        if a is b:
            continue
        wire(a, b, rng.uniform(18, 95), "CA->CA", t0 + timedelta(hours=rng.randint(3, 200)), "normal", purpose="noise")

    levy = acc("LEVY", "CA", 2400)
    for i in range(8):
        p = acc("PAYR", "CA", rng.randint(300, 1500))
        wire(p, levy, rng.uniform(40, 160), "CA->CA", t0 + timedelta(days=i * 2.2), "ambiguous_levy", purpose="levy")

    dues = acc("DUES", "MX", 1900)
    for i in range(8):
        m = acc("MEM", "MX", rng.randint(400, 1600))
        wire(m, dues, rng.uniform(15, 70), "MX->MX", t0 + timedelta(days=i * 1.6), "ambiguous_dues", currency="MXN", purpose="dues")

    a = acc("PEEL", "CA", 5)
    b = acc("PEELB", "CA", 6)
    for i in range(3):
        if i % 2 == 0:
            wire(a, b, 9800, "CA->CA", t0 + timedelta(days=70, minutes=i * 22), "round_trip_peel", purpose="swap")
        else:
            wire(b, a, 9750, "CA->CA", t0 + timedelta(days=70, minutes=i * 22), "round_trip_peel", purpose="swap")
    for i in range(4):
        cash = acc("CASH", "MX", rng.randint(2, 9))
        wire(b, cash, rng.uniform(2100, 2500), "CA->MX", t0 + timedelta(days=70, hours=2, minutes=i * 14), "round_trip_peel", currency="MXN", purpose="cashout")

    hops = [acc("SKIP", "MX", rng.randint(3, 9)) for _ in range(5)]
    amts = [16000, 12500, 9800, 7200, 5100]
    for i in range(4):
        if i == 2:
            continue
        wire(hops[i], hops[i + 1], amts[i], "MX->MX", t0 + timedelta(days=75, minutes=i * 45), "skip_hop", currency="MXN", purpose="layer")
    ext = acc("OFF", "MX", 11)
    wire(hops[-1], ext, 4300, "MX->??", t0 + timedelta(days=75, hours=4), "skip_hop", currency="MXN", purpose="offbook")

    sleeper = acc("OLD", "CA", 2100)
    inj = acc("INJ", "MX", 4)
    wire(inj, sleeper, 41000, "MX->CA", t0 + timedelta(days=80), "dormant_drain", currency="MXN", purpose="inject")
    for i in range(5):
        out = acc("DRAIN", "CA", rng.randint(3, 11))
        wire(sleeper, out, rng.uniform(6800, 8400), "CA->CA", t0 + timedelta(days=80, minutes=18 + i * 22), "dormant_drain", purpose="peel")

    sink = acc("PULSE", "CA", 4)
    for i in range(16):
        src = acc("DRIP", "MX", rng.randint(2, 8))
        wire(src, sink, rng.uniform(350, 620), "MX->CA", t0 + timedelta(days=90, seconds=i * 32), "pulse_smurf", currency="MXN", purpose="smurf")

    return accounts, txns
