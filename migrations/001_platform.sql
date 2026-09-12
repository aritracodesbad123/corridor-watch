-- Additive platform tables. Applied by db.init_schema() for SQLite and PostgreSQL.
-- Do not generate synthetic data during image build.

CREATE TABLE IF NOT EXISTS banks (
    bank_id TEXT PRIMARY KEY,
    name TEXT,
    country TEXT,
    institution_type TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_events (
    message_id TEXT PRIMARY KEY,
    txn_id TEXT,
    received_at TEXT,
    source TEXT
);

CREATE TABLE IF NOT EXISTS investigation_queue (
    queue_id TEXT PRIMARY KEY,
    txn_id TEXT,
    network_id TEXT,
    risk_tier TEXT,
    status TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS investigations (
    case_id TEXT PRIMARY KEY,
    created_at TEXT,
    updated_at TEXT,
    status TEXT,
    risk_level TEXT,
    primary_txn_id TEXT,
    network_id TEXT,
    pattern_ids TEXT,
    ai_summary TEXT,
    ai_hypothesis TEXT,
    confidence REAL,
    analyst_decision TEXT,
    assigned_role TEXT
);

CREATE TABLE IF NOT EXISTS crime_patterns (
    pattern_id TEXT PRIMARY KEY,
    version INTEGER,
    name TEXT,
    description TEXT,
    entry_signals TEXT,
    movement_signals TEXT,
    relationship_signals TEXT,
    geography_signals TEXT,
    timing_signals TEXT,
    exit_signals TEXT,
    graph_signature TEXT,
    temporal_signature TEXT,
    corridor_signature TEXT,
    created_at TEXT,
    created_by TEXT,
    active INTEGER,
    confirmed_cases INTEGER
);

CREATE TABLE IF NOT EXISTS pattern_matches (
    match_id TEXT PRIMARY KEY,
    pattern_id TEXT,
    txn_id TEXT,
    case_id TEXT,
    score REAL,
    evidence TEXT,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_txn_ts ON transactions(ts);
CREATE INDEX IF NOT EXISTS idx_txn_sender_ts ON transactions(sender_id, ts);
CREATE INDEX IF NOT EXISTS idx_txn_receiver_ts ON transactions(receiver_id, ts);
CREATE INDEX IF NOT EXISTS idx_investigations_status ON investigations(status);
CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_log(case_id);
