"""
Synthetic accounts, transactions, devices, beneficiaries, and sessions.
Injects five fraud scenarios so graph + agent layers have clear signals:
  1. mule_pass_through — fan-in into fresh mule, near-total out within hours
  2. split_transaction_laundering — many sub-threshold feeds into one sink
  3. shared_device_ring — unrelated accounts sharing device fingerprints
  4. synthetic_identity — new accounts with geo/occupation/income mismatch
  5. multi_hop_chain — layered hops across intermediate accounts
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

from faker import Faker

from db import DB_PATH, connect, init_schema

fake = Faker()
random.seed(42)
Faker.seed(42)

CORRIDORS = [("IN", "SG"), ("PH", "AE"), ("ID", "SG"), ("VN", "US"), ("IN", "US"), ("PH", "US")]
NOW = datetime(2026, 9, 1)
DEVICES: list[dict] = []
BENEFICIARIES: list[dict] = []
ACCOUNT_DEVICES: list[dict] = []
ACCOUNT_BENEFS: list[dict] = []
SESSIONS: list[dict] = []


def uid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def new_account(country: str, days_old: int, occupation: str | None = None,
                income: float | None = None, fraud_label: str = "normal") -> dict:
    return {
        "account_id": uid("A"),
        "name": fake.name(),
        "country": country,
        "opened_date": (NOW - timedelta(days=days_old)).isoformat(),
        "occupation": occupation or fake.job(),
        "stated_income_usd": income if income is not None else round(random.uniform(8_000, 45_000), 2),
        "kyc_tier": random.choice(["basic", "standard", "enhanced"]),
        "fraud_label": fraud_label,
    }


def new_device(first_seen_days: int = 30) -> dict:
    d = {
        "device_id": uid("D"),
        "fingerprint": fake.sha1()[:16],
        "first_seen": (NOW - timedelta(days=first_seen_days)).isoformat(),
        "os": random.choice(["Android 14", "iOS 18", "Windows 11", "ChromeOS"]),
    }
    DEVICES.append(d)
    return d


def new_beneficiary(country: str) -> dict:
    b = {
        "beneficiary_id": uid("B"),
        "name": fake.name(),
        "country": country,
        "bank_hint": fake.company()[:24],
    }
    BENEFICIARIES.append(b)
    return b


def link_device(account_id: str, device_id: str, days_ago: int = 1) -> None:
    ACCOUNT_DEVICES.append({
        "account_id": account_id,
        "device_id": device_id,
        "linked_at": (NOW - timedelta(days=days_ago)).isoformat(),
    })


def link_benef(account_id: str, beneficiary_id: str, days_ago: int = 1) -> None:
    ACCOUNT_BENEFS.append({
        "account_id": account_id,
        "beneficiary_id": beneficiary_id,
        "added_at": (NOW - timedelta(days=days_ago)).isoformat(),
    })


def make_session(account_id: str, device_id: str, ts: datetime, risky: bool = False) -> dict:
    if risky:
        sess = {
            "session_id": uid("S"),
            "account_id": account_id,
            "device_id": device_id,
            "started_at": ts.isoformat(),
            "typing_deviation": round(random.uniform(2.4, 4.5), 2),
            "navigation_velocity": round(random.uniform(3.5, 6.0), 2),
            "bot_likelihood": round(random.uniform(0.55, 0.95), 2),
            "copy_paste_risk": round(random.uniform(0.6, 0.99), 2),
            "geo_mismatch": 1,
        }
    else:
        sess = {
            "session_id": uid("S"),
            "account_id": account_id,
            "device_id": device_id,
            "started_at": ts.isoformat(),
            "typing_deviation": round(random.uniform(0.2, 1.2), 2),
            "navigation_velocity": round(random.uniform(0.4, 1.8), 2),
            "bot_likelihood": round(random.uniform(0.02, 0.25), 2),
            "copy_paste_risk": round(random.uniform(0.01, 0.3), 2),
            "geo_mismatch": 0 if random.random() > 0.08 else 1,
        }
    SESSIONS.append(sess)
    return sess


def txn(sender, receiver, amount, corridor, ts, device_id=None, session_id=None,
        beneficiary_id=None, purpose="family support", sof="salary",
        fraud_scenario="normal") -> dict:
    return {
        "txn_id": uid("T"),
        "sender_id": sender,
        "receiver_id": receiver,
        "amount": round(amount, 2),
        "currency": "USD",
        "corridor": corridor,
        "ts": ts.isoformat() if isinstance(ts, datetime) else ts,
        "device_id": device_id,
        "session_id": session_id,
        "beneficiary_id": beneficiary_id,
        "purpose": purpose,
        "source_of_funds": sof,
        "fraud_scenario": fraud_scenario,
    }


def build():
    accounts: list[dict] = []
    txns: list[dict] = []

    # ---- normal remittance population ----
    for _ in range(160):
        src, dst = random.choice(CORRIDORS)
        acc = new_account(src, days_old=random.randint(200, 2200))
        accounts.append(acc)
        device = new_device(first_seen_days=random.randint(60, 800))
        link_device(acc["account_id"], device["device_id"], days_ago=random.randint(30, 400))
        benef = new_beneficiary(dst)
        link_benef(acc["account_id"], benef["beneficiary_id"], days_ago=random.randint(10, 200))
        for _ in range(random.randint(1, 5)):
            ts = NOW - timedelta(days=random.randint(0, 180), hours=random.randint(0, 23))
            sess = make_session(acc["account_id"], device["device_id"], ts, risky=False)
            txns.append(txn(
                acc["account_id"], "EXT-" + fake.iban()[:10],
                random.uniform(50, 2000), f"{src}->{dst}", ts,
                device["device_id"], sess["session_id"], benef["beneficiary_id"],
                purpose=random.choice(["family support", "education", "medical", "rent"]),
                sof=random.choice(["salary", "savings", "business income"]),
            ))

    # ---- 1. mule pass-through rings ----
    for ring in range(4):
        src, dst = random.choice(CORRIDORS)
        mule = new_account(dst, days_old=random.randint(2, 6), fraud_label="mule_pass_through")
        accounts.append(mule)
        mule_dev = new_device(first_seen_days=random.randint(1, 5))
        link_device(mule["account_id"], mule_dev["device_id"], days_ago=2)
        collector = "EXT-COLLECTOR-" + str(ring)
        inflow = 0.0
        base = NOW - timedelta(days=random.randint(1, 10))
        for _ in range(random.randint(6, 10)):
            feeder = new_account(src, days_old=random.randint(1, 8), fraud_label="mule_feeder")
            accounts.append(feeder)
            fdev = new_device(first_seen_days=3)
            link_device(feeder["account_id"], fdev["device_id"], days_ago=1)
            amt = random.uniform(300, 900)
            inflow += amt
            ts = base + timedelta(hours=random.randint(0, 18))
            sess = make_session(feeder["account_id"], fdev["device_id"], ts, risky=True)
            txns.append(txn(
                feeder["account_id"], mule["account_id"], amt, f"{src}->{dst}", ts,
                fdev["device_id"], sess["session_id"], purpose="business payment",
                sof="client funds", fraud_scenario="mule_pass_through",
            ))
        out_ts = base + timedelta(hours=22)
        sess = make_session(mule["account_id"], mule_dev["device_id"], out_ts, risky=True)
        txns.append(txn(
            mule["account_id"], collector, inflow * random.uniform(0.9, 0.98),
            f"{dst}->AE", out_ts, mule_dev["device_id"], sess["session_id"],
            purpose="settlement", sof="received remittance",
            fraud_scenario="mule_pass_through",
        ))

    # ---- 2. split-transaction laundering ----
    for _ in range(3):
        src, dst = random.choice(CORRIDORS)
        sink = new_account(dst, days_old=random.randint(5, 20), fraud_label="split_laundering")
        accounts.append(sink)
        sink_dev = new_device(5)
        link_device(sink["account_id"], sink_dev["device_id"], 3)
        shared_benef = new_beneficiary(dst)
        link_benef(sink["account_id"], shared_benef["beneficiary_id"], 2)
        base = NOW - timedelta(days=random.randint(2, 8))
        for i in range(12):
            feeder = new_account(src, days_old=random.randint(30, 400), fraud_label="split_feeder")
            accounts.append(feeder)
            fdev = new_device(40)
            link_device(feeder["account_id"], fdev["device_id"], 10)
            link_benef(feeder["account_id"], shared_benef["beneficiary_id"], 1)
            ts = base + timedelta(hours=i * 2)
            sess = make_session(feeder["account_id"], fdev["device_id"], ts, risky=True)
            txns.append(txn(
                feeder["account_id"], sink["account_id"], random.uniform(480, 990),
                f"{src}->{dst}", ts, fdev["device_id"], sess["session_id"],
                shared_benef["beneficiary_id"], purpose="goods payment",
                sof="sale proceeds", fraud_scenario="split_transaction_laundering",
            ))

    # ---- 3. shared-device rings ----
    for _ in range(3):
        shared = new_device(first_seen_days=2)
        src, dst = random.choice(CORRIDORS)
        ring_accounts = []
        for _ in range(5):
            acc = new_account(src, days_old=random.randint(1, 10), fraud_label="shared_device_ring")
            accounts.append(acc)
            link_device(acc["account_id"], shared["device_id"], days_ago=1)
            ring_accounts.append(acc)
        for acc in ring_accounts:
            ts = NOW - timedelta(hours=random.randint(1, 48))
            sess = make_session(acc["account_id"], shared["device_id"], ts, risky=True)
            txns.append(txn(
                acc["account_id"], "EXT-" + fake.iban()[:10],
                random.uniform(700, 2500), f"{src}->{dst}", ts,
                shared["device_id"], sess["session_id"],
                purpose="family support", sof="salary",
                fraud_scenario="shared_device_ring",
            ))

    # ---- 4. synthetic identity ----
    for _ in range(5):
        country = random.choice(["SG", "AE", "US"])
        acc = new_account(
            country=country,
            days_old=random.randint(1, 4),
            occupation=random.choice(["Unemployed", "Student", "Intern"]),
            income=random.uniform(0, 4000),
            fraud_label="synthetic_identity",
        )
        accounts.append(acc)
        device = new_device(1)
        link_device(acc["account_id"], device["device_id"], 1)
        for _ in range(random.randint(3, 6)):
            ts = NOW - timedelta(hours=random.randint(0, 72))
            sess = make_session(acc["account_id"], device["device_id"], ts, risky=True)
            txns.append(txn(
                "EXT-" + fake.iban()[:10], acc["account_id"],
                random.uniform(4000, 9500), f"??->{country}", ts,
                device["device_id"], sess["session_id"],
                purpose="investment", sof="inheritance",
                fraud_scenario="synthetic_identity",
            ))

    # ---- 5. multi-hop layering chains ----
    for _ in range(3):
        src, dst = random.choice(CORRIDORS)
        hops = []
        for i in range(4):
            country = src if i == 0 else (dst if i == 3 else random.choice([src, dst, "AE"]))
            acc = new_account(country, days_old=random.randint(3, 25), fraud_label="multi_hop_chain")
            accounts.append(acc)
            dev = new_device(4)
            link_device(acc["account_id"], dev["device_id"], 2)
            hops.append((acc, dev))
        base = NOW - timedelta(days=random.randint(1, 5))
        amount = random.uniform(5000, 12000)
        for i in range(len(hops) - 1):
            a, da = hops[i]
            b, _ = hops[i + 1]
            ts = base + timedelta(hours=i * 6 + random.randint(0, 2))
            sess = make_session(a["account_id"], da["device_id"], ts, risky=True)
            txns.append(txn(
                a["account_id"], b["account_id"], amount * random.uniform(0.92, 0.99),
                f"{a['country']}->{b['country']}", ts, da["device_id"], sess["session_id"],
                purpose="intercompany", sof="business float",
                fraud_scenario="multi_hop_chain",
            ))

    return accounts, txns


def write_db(accounts, txns):
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = connect(row_factory=False)
    init_schema(con)
    cur = con.cursor()
    cur.executemany(
        "INSERT INTO accounts VALUES (:account_id,:name,:country,:opened_date,"
        ":occupation,:stated_income_usd,:kyc_tier,:fraud_label)",
        accounts,
    )
    cur.executemany(
        "INSERT INTO devices VALUES (:device_id,:fingerprint,:first_seen,:os)", DEVICES
    )
    cur.executemany(
        "INSERT INTO account_devices VALUES (:account_id,:device_id,:linked_at)", ACCOUNT_DEVICES
    )
    cur.executemany(
        "INSERT INTO beneficiaries VALUES (:beneficiary_id,:name,:country,:bank_hint)",
        BENEFICIARIES,
    )
    cur.executemany(
        "INSERT INTO account_beneficiaries VALUES (:account_id,:beneficiary_id,:added_at)",
        ACCOUNT_BENEFS,
    )
    cur.executemany(
        "INSERT INTO sessions VALUES (:session_id,:account_id,:device_id,:started_at,"
        ":typing_deviation,:navigation_velocity,:bot_likelihood,:copy_paste_risk,:geo_mismatch)",
        SESSIONS,
    )
    cur.executemany(
        "INSERT INTO transactions VALUES (:txn_id,:sender_id,:receiver_id,:amount,:currency,"
        ":corridor,:ts,:device_id,:session_id,:beneficiary_id,:purpose,:source_of_funds,:fraud_scenario)",
        txns,
    )
    con.commit()
    con.close()


if __name__ == "__main__":
    accounts, txns = build()
    write_db(accounts, txns)
    # Always materialize derived risk scores/alerts after regenerating the source data.
    # This keeps a fresh demo database immediately runnable and makes evaluation reproducible.
    from graph_features import score_all, write_scores
    con = connect()
    scores, _, _ = score_all(con)
    flagged = write_scores(con, scores, txns)
    con.close()
    print(
        f"accounts={len(accounts)} txns={len(txns)} devices={len(DEVICES)} "
        f"sessions={len(SESSIONS)} beneficiaries={len(BENEFICIARIES)} flagged={flagged} -> {DB_PATH.name}"
    )
