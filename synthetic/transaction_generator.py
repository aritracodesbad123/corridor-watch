"""Generate correlated synthetic events for ingest / load tests."""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

from pubsub.schemas import TransactionEvent
from synthetic.fraud_patterns import CAMPAIGNS
from synthetic.world import CORRIDORS, bank_for


def _txn_id(prefix: str = "L") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _account(prefix: str, rng: random.Random) -> str:
    return f"{prefix}{rng.randrange(10_000, 99_999)}"


def generate_events(
    n: int,
    *,
    seed: int = 42,
    scenario_mix: str = "default",
    now: datetime | None = None,
) -> list[TransactionEvent]:
    rng = random.Random(seed)
    now = now or datetime.now(timezone.utc)
    events: list[TransactionEvent] = []
    fraud_ratio = 0.04 if scenario_mix == "default" else 0.12
    remaining = n
    while remaining > 0:
        if rng.random() < fraud_ratio and remaining >= 6:
            campaign = rng.choice(CAMPAIGNS)
            batch = _campaign_events(campaign.name, rng, now)
            events.extend(batch)
            remaining -= len(batch)
        else:
            events.append(_normal_event(rng, now))
            remaining -= 1
    return events[:n]


def _normal_event(rng: random.Random, now: datetime) -> TransactionEvent:
    src, dst = rng.choice(CORRIDORS)
    ts = now - timedelta(seconds=rng.randint(0, 3600))
    return TransactionEvent(
        txn_id=_txn_id("N"),
        timestamp=ts.isoformat(),
        sender_account_id=_account("A", rng),
        receiver_account_id=_account("EXT", rng),
        amount=round(rng.uniform(40, 1800), 2),
        origin_country=src,
        destination_country=dst,
        origin_bank_id=bank_for(src),
        destination_bank_id=bank_for(dst),
        channel="remittance",
        purpose=rng.choice(["family support", "education", "medical", "rent"]),
        source_of_funds=rng.choice(["salary", "savings", "business income"]),
        fraud_scenario="normal",
        account_age_days=rng.randint(200, 2200),
    )


def _campaign_events(name: str, rng: random.Random, now: datetime) -> list[TransactionEvent]:
    src, dst = rng.choice(CORRIDORS)
    scenario_id = f"{name}-{uuid.uuid4().hex[:6]}"
    if name == "mule_pass_through":
        mule = _account("MULE", rng)
        victim = _account("VIC", rng)
        hop_b = _account("MULEB", rng)
        hop_c = _account("MULEC", rng)
        benef = _account("BEN", rng)
        device = f"D{rng.randrange(10000, 99999)}"
        base = now - timedelta(minutes=rng.randint(10, 80))
        chain = [victim, mule, hop_b, hop_c, benef]
        countries = [src, dst, dst, "AE", "AE"]
        banks = [bank_for(src), bank_for(dst), bank_for(dst), "PAYMENT_PROVIDER_X", "BANK_AE"]
        out = []
        amount = round(rng.uniform(1200, 2800), 2)
        for i in range(len(chain) - 1):
            ts = base + timedelta(minutes=i * 8)
            out.append(TransactionEvent(
                txn_id=_txn_id("F"),
                timestamp=ts.isoformat(),
                sender_account_id=chain[i],
                receiver_account_id=chain[i + 1],
                amount=round(amount * (0.92 ** i), 2),
                origin_country=countries[i],
                destination_country=countries[i + 1],
                origin_bank_id=banks[i],
                destination_bank_id=banks[i + 1],
                device_id=device,
                beneficiary_id=benef,
                purpose="settlement",
                source_of_funds="client funds",
                fraud_scenario="mule_pass_through",
                scenario_id=scenario_id,
                account_age_days=rng.randint(1, 6),
            ))
        return out

    if name in {"fan_in_fan_out", "shared_beneficiary_ring", "structuring"}:
        sink = _account("SINK", rng)
        exit_acct = _account("EXIT", rng)
        benef = f"B{rng.randrange(10000, 99999)}"
        feeders = [_account("FEED", rng) for _ in range(5)]
        out = []
        base = now - timedelta(minutes=40)
        total = 0.0
        for i, feeder in enumerate(feeders):
            amt = round(rng.uniform(480, 990), 2)
            total += amt
            out.append(TransactionEvent(
                txn_id=_txn_id("F"),
                timestamp=(base + timedelta(minutes=i * 3)).isoformat(),
                sender_account_id=feeder,
                receiver_account_id=sink,
                amount=amt,
                origin_country=src,
                destination_country=dst,
                origin_bank_id=bank_for(src),
                destination_bank_id=bank_for(dst),
                beneficiary_id=benef,
                purpose="goods payment",
                source_of_funds="sale proceeds",
                fraud_scenario="split_transaction_laundering",
                scenario_id=scenario_id,
                account_age_days=rng.randint(2, 20),
            ))
        if name != "shared_beneficiary_ring":
            out.append(TransactionEvent(
                txn_id=_txn_id("F"),
                timestamp=(base + timedelta(minutes=25)).isoformat(),
                sender_account_id=sink,
                receiver_account_id=exit_acct,
                amount=round(total * 0.94, 2),
                origin_country=dst,
                destination_country="AE",
                origin_bank_id=bank_for(dst),
                destination_bank_id="PAYMENT_PROVIDER_X",
                beneficiary_id=benef,
                purpose="settlement",
                source_of_funds="received remittance",
                fraud_scenario="split_transaction_laundering",
                scenario_id=scenario_id,
                account_age_days=4,
            ))
        return out

    if name == "shared_device_ring":
        device = f"DSHARE{rng.randrange(1000, 9999)}"
        out = []
        for _ in range(5):
            acc = _account("RING", rng)
            out.append(TransactionEvent(
                txn_id=_txn_id("F"),
                timestamp=(now - timedelta(minutes=rng.randint(1, 90))).isoformat(),
                sender_account_id=acc,
                receiver_account_id=_account("EXT", rng),
                amount=round(rng.uniform(700, 2400), 2),
                origin_country=src,
                destination_country=dst,
                origin_bank_id=bank_for(src),
                destination_bank_id=bank_for(dst),
                device_id=device,
                purpose="family support",
                source_of_funds="salary",
                fraud_scenario="shared_device_ring",
                scenario_id=scenario_id,
                account_age_days=rng.randint(1, 9),
            ))
        return out

    if name in {"multi_hop_chain", "cross_institution_movement"}:
        hops = [_account("HOP", rng) for _ in range(4)]
        countries = [src, dst, "SG", "AE"]
        banks = [bank_for(src), bank_for(dst), "PAYMENT_PROVIDER_X", "BANK_AE"]
        amount = round(rng.uniform(5000, 11000), 2)
        out = []
        base = now - timedelta(hours=2)
        for i in range(3):
            out.append(TransactionEvent(
                txn_id=_txn_id("F"),
                timestamp=(base + timedelta(minutes=i * 25)).isoformat(),
                sender_account_id=hops[i],
                receiver_account_id=hops[i + 1],
                amount=round(amount * (0.95 ** i), 2),
                origin_country=countries[i],
                destination_country=countries[i + 1],
                origin_bank_id=banks[i],
                destination_bank_id=banks[i + 1],
                purpose="intercompany",
                source_of_funds="business float",
                fraud_scenario="multi_hop_chain",
                scenario_id=scenario_id,
                account_age_days=rng.randint(3, 20),
            ))
        return out

    # synthetic identity
    acc = _account("SYN", rng)
    device = f"DNEW{rng.randrange(1000, 9999)}"
    out = []
    for i in range(4):
        out.append(TransactionEvent(
            txn_id=_txn_id("F"),
            timestamp=(now - timedelta(minutes=i * 15)).isoformat(),
            sender_account_id=_account("EXT", rng),
            receiver_account_id=acc,
            amount=round(rng.uniform(4000, 9000), 2),
            origin_country="??",
            destination_country=dst,
            origin_bank_id="PAYMENT_PROVIDER_X",
            destination_bank_id=bank_for(dst),
            device_id=device,
            purpose="investment",
            source_of_funds="inheritance",
            fraud_scenario="synthetic_identity",
            scenario_id=scenario_id,
            account_age_days=rng.randint(1, 4),
        ))
    return out
