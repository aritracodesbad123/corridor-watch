"""Shared SQLite helpers and schema bootstrap."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "fraud_demo.db"


def connect(row_factory: bool = True) -> sqlite3.Connection:
    # WAL + timeout makes concurrent API/audit writes much safer for the local POC.
    con = sqlite3.connect(DB_PATH, timeout=10.0)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    if row_factory:
        con.row_factory = sqlite3.Row
    return con


SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    name TEXT,
    country TEXT,
    opened_date TEXT,
    occupation TEXT,
    stated_income_usd REAL,
    kyc_tier TEXT,
    fraud_label TEXT
);

CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    fingerprint TEXT,
    first_seen TEXT,
    os TEXT
);

CREATE TABLE IF NOT EXISTS account_devices (
    account_id TEXT,
    device_id TEXT,
    linked_at TEXT,
    PRIMARY KEY (account_id, device_id)
);

CREATE TABLE IF NOT EXISTS beneficiaries (
    beneficiary_id TEXT PRIMARY KEY,
    name TEXT,
    country TEXT,
    bank_hint TEXT
);

CREATE TABLE IF NOT EXISTS account_beneficiaries (
    account_id TEXT,
    beneficiary_id TEXT,
    added_at TEXT,
    PRIMARY KEY (account_id, beneficiary_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    account_id TEXT,
    device_id TEXT,
    started_at TEXT,
    typing_deviation REAL,
    navigation_velocity REAL,
    bot_likelihood REAL,
    copy_paste_risk REAL,
    geo_mismatch INTEGER
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id TEXT PRIMARY KEY,
    sender_id TEXT,
    receiver_id TEXT,
    amount REAL,
    currency TEXT,
    corridor TEXT,
    ts TEXT,
    device_id TEXT,
    session_id TEXT,
    beneficiary_id TEXT,
    purpose TEXT,
    source_of_funds TEXT,
    fraud_scenario TEXT
);

CREATE TABLE IF NOT EXISTS risk_scores (
    account_id TEXT PRIMARY KEY,
    risk_score REAL,
    fan_in_count INT,
    fan_out_count INT,
    pass_through_ratio REAL,
    avg_hold_time_minutes REAL,
    shared_device_count INT,
    shared_beneficiary_count INT,
    multi_hop_chain_depth INT,
    account_age_days INT,
    corridor_velocity_score REAL,
    behavioral_risk REAL,
    primary_pattern TEXT,
    pattern_scores TEXT
);

CREATE TABLE IF NOT EXISTS flagged_transactions (
    txn_id TEXT PRIMARY KEY,
    sender_id TEXT,
    receiver_id TEXT,
    amount REAL,
    corridor TEXT,
    ts TEXT,
    risk_score REAL,
    primary_pattern TEXT,
    fraud_scenario TEXT,
    currency TEXT,
    purpose TEXT,
    source_of_funds TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,
    case_id TEXT,
    actor TEXT,
    event_type TEXT,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS investigation_runs (
    run_id TEXT PRIMARY KEY,
    txn_id TEXT,
    started_at TEXT,
    finished_at TEXT,
    mode TEXT,
    status TEXT,
    dag_trace TEXT,
    verdict TEXT
);

CREATE TABLE IF NOT EXISTS analyst_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_id TEXT,
    decided_at TEXT,
    decision TEXT,
    notes TEXT,
    analyst_id TEXT
);

CREATE TABLE IF NOT EXISTS case_memory (
    case_id TEXT PRIMARY KEY,
    pattern TEXT,
    summary TEXT,
    outcome TEXT,
    corridor TEXT,
    risk_level TEXT,
    created_at TEXT,
    embedding_text TEXT
);

CREATE TABLE IF NOT EXISTS redteam_scenarios (
    scenario_id TEXT PRIMARY KEY,
    created_at TEXT,
    pattern_name TEXT,
    description TEXT,
    injected INTEGER,
    detected INTEGER,
    evasion_reason TEXT,
    payload TEXT
);

CREATE TABLE IF NOT EXISTS verdicts (
    txn_id TEXT PRIMARY KEY,
    verdict TEXT,
    created_at TEXT,
    mode TEXT
);
"""


def init_schema(con: sqlite3.Connection | None = None) -> None:
    own = con is None
    if own:
        con = connect(row_factory=False)
    con.executescript(SCHEMA)
    con.commit()
    if own:
        con.close()
