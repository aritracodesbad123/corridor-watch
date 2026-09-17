"""Distribution G — GenAI unknown holdout. Not Dist F.

Frozen seed 53. Novel fraud names never used in Dist A–F or golden first-100.
JPY/KRW, 2019 clock, airport–freight–retail. Runtime ignores fraud_scenario.
GenAI eval only — do not treat as detector Dist A–F evidence.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

SEED = 53
NOW = datetime(2026, 9, 1)
POSITIVE_G = {"tarmac_drip", "gate_skip", "cargo_wake", "airbill_loop"}
KNOWN_A_TO_F = {
    "mule_pass_through", "split_transaction_laundering", "shared_device_ring",
    "synthetic_identity", "multi_hop_chain", "circular_pass", "burst_smurf",
    "layering_cascade", "dormant_wake", "funnel_exit", "mirror_peel",
    "invoice_loop", "nested_shell", "drain_wake", "burst_sink",
    "round_trip_peel", "skip_hop", "dormant_drain", "pulse_smurf",
    "dock_smurf", "berth_skip", "quay_wake", "trade_overbill",
}


def build(*, seed: int = SEED) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    t0 = datetime(2019, 4, 3, 7, 40, 0)
    accounts: list[dict] = []
    txns: list[dict] = []

    def acc(prefix: str, country: str, age: int) -> dict:
        row = {
            "account_id": f"G-{prefix}-{len(accounts):04d}",
            "name": f"{prefix} {len(accounts)}",
            "country": country,
            "opened_date": (NOW - timedelta(days=age)).date().isoformat(),
            "occupation": "ops",
            "stated_income_usd": 61000,
            "kyc_tier": "standard",
            "fraud_label": 0,
            "bank_id": f"BANK_{country}",
            "account_age_days": age,
        }
        accounts.append(row)
        return row

    def wire(a, b, amount, corridor, ts, scenario, currency="JPY", purpose="settlement"):
        txns.append({
            "txn_id": f"G-{len(txns):04d}-{scenario[:3].upper()}",
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

    airports = [acc("APT", "JP", rng.randint(700, 2200)) for _ in range(5)]
    freight = [acc("FRT", "JP", rng.randint(800, 2400)) for _ in range(4)]
    retail = [acc("RET", "KR", rng.randint(500, 1900)) for _ in range(5)]
    for i, apt in enumerate(airports):
        fr = freight[i % len(freight)]
        wire(apt, fr, rng.uniform(2200, 6800), "JP->JP", t0 + timedelta(days=i * 5), "normal", purpose="cargo")
    for i, fr in enumerate(freight):
        shop = retail[i % len(retail)]
        wire(fr, shop, rng.uniform(1400, 4500), "JP->KR", t0 + timedelta(days=3 + i * 5), "normal", currency="KRW", purpose="wholesale")

    co = acc("DIVJP", "JP", 2500)
    for i in range(6):
        sh = acc("HOLD", "JP", rng.randint(400, 1800))
        wire(co, sh, rng.uniform(0.25, 1.1), "JP->JP", t0 + timedelta(days=45 + i), "normal", purpose="dividend")

    for i in range(3):
        a, b = acc("KRA", "KR", rng.randint(600, 1800)), acc("JPB", "JP", rng.randint(500, 1700))
        amt = rng.uniform(12000, 18000)
        wire(a, b, amt, "KR->JP", t0 + timedelta(days=14 + i * 6), "normal", currency="KRW", purpose="trade")
        wire(b, a, amt * rng.uniform(0.96, 1.02), "JP->KR", t0 + timedelta(days=16 + i * 6), "normal", purpose="trade")

    pool = freight + retail
    for i in range(14):
        a, b = rng.choice(pool), rng.choice(pool)
        if a is b:
            continue
        wire(a, b, rng.uniform(16, 85), "JP->KR", t0 + timedelta(hours=rng.randint(4, 160)), "normal", currency="KRW", purpose="noise")

    shrine = acc("SHRINE", "JP", 2300)
    for i in range(8):
        d = acc("DON", "JP", rng.randint(300, 1400))
        wire(d, shrine, rng.uniform(22, 95), "JP->JP", t0 + timedelta(days=i * 2.1), "ambiguous_shrine", purpose="gift")

    guild = acc("GUILD", "KR", 1700)
    for i in range(7):
        m = acc("MEM", "KR", rng.randint(400, 1500))
        wire(m, guild, rng.uniform(14, 58), "KR->KR", t0 + timedelta(days=i * 1.8), "ambiguous_guild", currency="KRW", purpose="dues")

    # Novel fraud — names disjoint from Dist A–F
    sink = acc("TARMAC", "JP", 5)
    for i in range(14):
        src = acc("DRIP", "KR", rng.randint(2, 8))
        wire(src, sink, rng.uniform(390, 660), "KR->JP", t0 + timedelta(days=70, seconds=i * 30), "tarmac_drip", currency="KRW", purpose="smurf")

    hops = [acc("GATE", "KR", rng.randint(3, 8)) for _ in range(5)]
    amts = [15500, 12100, 9400, 7100, 4900]
    for i in range(4):
        if i == 2:
            continue
        wire(hops[i], hops[i + 1], amts[i], "KR->KR", t0 + timedelta(days=75, minutes=i * 42), "gate_skip", currency="KRW", purpose="layer")
    ext = acc("OFF", "KR", 10)
    wire(hops[-1], ext, 4000, "KR->??", t0 + timedelta(days=75, hours=4), "gate_skip", currency="KRW", purpose="offbook")

    sleeper = acc("CARGO", "JP", 2000)
    inj = acc("INJ", "KR", 4)
    wire(inj, sleeper, 37000, "KR->JP", t0 + timedelta(days=80), "cargo_wake", currency="KRW", purpose="inject")
    for i in range(5):
        out = acc("DRAIN", "JP", rng.randint(3, 10))
        wire(sleeper, out, rng.uniform(6200, 7900), "JP->JP", t0 + timedelta(days=80, minutes=16 + i * 21), "cargo_wake", purpose="peel")

    a = acc("AIRB", "JP", 6)
    b = acc("AIRBB", "KR", 5)
    for i in range(4):
        wire(a, b, 24500 + i * 400, "JP->KR", t0 + timedelta(days=85, minutes=i * 28), "airbill_loop", purpose="invoice")
        wire(b, a, 24200 + i * 350, "KR->JP", t0 + timedelta(days=85, minutes=12 + i * 28), "airbill_loop", currency="KRW", purpose="invoice")

    return accounts, txns
