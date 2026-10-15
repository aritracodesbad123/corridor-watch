"""Distribution H — structure holdout. Not Dist G.

Frozen seed 59. Topologies are not the Dist C–G skip-hop / 6-ring / pure-smurf /
inject-peel copy-paste cores. Scenario names disjoint from A–G.
BRL/ARS, 2017 clock. Runtime ignores fraud_scenario.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

SEED = 59
NOW = datetime(2026, 9, 1)
POSITIVE_H = {"spine_relay", "ring4_loop", "hub_braid", "mesh_clique", "noise_peel"}
KNOWN_A_TO_G = {
    "mule_pass_through", "split_transaction_laundering", "shared_device_ring",
    "synthetic_identity", "multi_hop_chain", "circular_pass", "burst_smurf",
    "layering_cascade", "dormant_wake", "funnel_exit", "mirror_peel",
    "invoice_loop", "nested_shell", "drain_wake", "burst_sink",
    "round_trip_peel", "skip_hop", "dormant_drain", "pulse_smurf",
    "dock_smurf", "berth_skip", "quay_wake", "trade_overbill",
    "tarmac_drip", "gate_skip", "cargo_wake", "airbill_loop",
}


def build(*, seed: int = SEED) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    t0 = datetime(2017, 3, 14, 11, 15, 0)
    accounts: list[dict] = []
    txns: list[dict] = []

    def acc(prefix: str, country: str, age: int) -> dict:
        row = {
            "account_id": f"H-{prefix}-{len(accounts):04d}",
            "name": f"{prefix} {len(accounts)}",
            "country": country,
            "opened_date": (NOW - timedelta(days=age)).date().isoformat(),
            "occupation": "ops",
            "stated_income_usd": 55000,
            "kyc_tier": "standard",
            "fraud_label": 0,
            "bank_id": f"BANK_{country}",
            "account_age_days": age,
        }
        accounts.append(row)
        return row

    def wire(a, b, amount, corridor, ts, scenario, currency="BRL", purpose="settlement"):
        txns.append({
            "txn_id": f"H-{len(txns):04d}-{scenario[:3].upper()}",
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

    # Benign background: farms → co-ops → exporters
    farms = [acc("FARM", "BR", rng.randint(600, 2200)) for _ in range(5)]
    coops = [acc("COOP", "BR", rng.randint(700, 2100)) for _ in range(4)]
    exporters = [acc("EXP", "AR", rng.randint(500, 1800)) for _ in range(4)]
    for i, farm in enumerate(farms):
        coop = coops[i % len(coops)]
        wire(farm, coop, rng.uniform(1600, 4800), "BR->BR", t0 + timedelta(days=i * 4), "normal", purpose="harvest")
    for i, coop in enumerate(coops):
        exp = exporters[i % len(exporters)]
        wire(coop, exp, rng.uniform(1200, 3900), "BR->AR", t0 + timedelta(days=2 + i * 4), "normal", currency="ARS", purpose="export")

    # Benign near-miss: old payroll fan-out
    payroll = acc("PAY", "BR", 2400)
    for i in range(10):
        staff = acc("STAFF", "BR", rng.randint(400, 1600))
        wire(payroll, staff, rng.uniform(2800, 4200), "BR->BR", t0 + timedelta(days=i), "benign_payroll", purpose="payroll")

    # Ambiguous dues (negative)
    union = acc("UNION", "AR", 1800)
    for i in range(7):
        mem = acc("MEM", "AR", rng.randint(300, 1400))
        wire(mem, union, rng.uniform(18, 70), "AR->AR", t0 + timedelta(days=i * 1.5), "ambiguous_dues", currency="ARS", purpose="dues")

    # spine_relay — continuous 6-hop (every hop present; Dist C–G skip index 2)
    hops = [acc("SPINE", "BR", rng.randint(3, 10)) for _ in range(7)]
    for i in range(6):
        wire(hops[i], hops[i + 1], 9200 - i * 700, "BR->BR", t0 + timedelta(days=60, minutes=i * 35), "spine_relay", purpose="relay")

    # ring4_loop — cycle length 4 (Dist B uses 6)
    ring = [acc("RING", "AR", rng.randint(8, 40)) for _ in range(4)]
    for i in range(4):
        wire(ring[i], ring[(i + 1) % 4], 6100 + i * 50, "AR->AR", t0 + timedelta(days=65, minutes=i * 22), "ring4_loop", currency="ARS", purpose="cycle")

    # hub_braid — fan-in into hub that also starts a chain
    hub = acc("BRAID", "BR", 4)
    for i in range(12):
        src = acc("IN", "AR", rng.randint(2, 9))
        wire(src, hub, rng.uniform(420, 680), "AR->BR", t0 + timedelta(days=70, seconds=i * 28), "hub_braid", currency="ARS", purpose="inflow")
    mid = [acc("MID", "BR", rng.randint(3, 8)) for _ in range(3)]
    wire(hub, mid[0], 5400, "BR->BR", t0 + timedelta(days=70, hours=2), "hub_braid", purpose="layer")
    wire(mid[0], mid[1], 5100, "BR->BR", t0 + timedelta(days=70, hours=2, minutes=25), "hub_braid", purpose="layer")
    wire(mid[1], mid[2], 4800, "BR->AR", t0 + timedelta(days=70, hours=3), "hub_braid", currency="ARS", purpose="exit")

    # mesh_clique — dense digraph on 5 nodes
    clique = [acc("MESH", "BR", rng.randint(10, 50)) for _ in range(5)]
    k = 0
    for i in range(5):
        for j in range(5):
            if i == j:
                continue
            wire(clique[i], clique[j], 1100 + k * 15, "BR->BR", t0 + timedelta(days=75, minutes=k * 8), "mesh_clique", purpose="mesh")
            k += 1

    # noise_peel — reciprocal peel amid dense normal noise
    bg = [acc("BG", "BR", rng.randint(400, 1600)) for _ in range(8)]
    for i in range(18):
        a, b = bg[i % 8], bg[(i + 3) % 8]
        wire(a, b, rng.uniform(40, 120), "BR->BR", t0 + timedelta(hours=i * 3), "normal", purpose="noise")
    peel_a = acc("PEEL", "BR", 5)
    peel_b = acc("PEELB", "AR", 6)
    for i in range(3):
        wire(peel_a, peel_b, 8800, "BR->AR", t0 + timedelta(days=80, minutes=i * 18), "noise_peel", purpose="swap")
        wire(peel_b, peel_a, 8700, "AR->BR", t0 + timedelta(days=80, minutes=8 + i * 18), "noise_peel", currency="ARS", purpose="swap")

    return accounts, txns
