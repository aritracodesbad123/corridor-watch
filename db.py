"""Shared persistence helpers.

Local default remains SQLite (`fraud_demo.db`). Set DATABASE_URL to a
postgresql:// URI for Cloud SQL-compatible deployments. Application modules
keep using `connect()` / `init_schema()` / `upsert()` — they must not import
sqlite3 directly for new platform tables.
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse, unquote

from config import get_settings

DB_PATH = Path(os.getenv("CW_DB_PATH") or (Path(__file__).resolve().parent / "fraud_demo.db"))


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

CREATE TABLE IF NOT EXISTS debates (
    txn_id TEXT PRIMARY KEY,
    payload TEXT,
    created_at TEXT
);
"""

PLATFORM_SCHEMA = """
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

CREATE TABLE IF NOT EXISTS outbox_events (
    outbox_id TEXT PRIMARY KEY,
    event_type TEXT,
    payload TEXT,
    created_at TEXT,
    published_at TEXT,
    attempts INTEGER,
    last_error TEXT
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

CREATE TABLE IF NOT EXISTS document_verifications (
    txn_id TEXT PRIMARY KEY,
    created_at TEXT,
    filename TEXT,
    mime_type TEXT,
    result TEXT
);

CREATE TABLE IF NOT EXISTS platform_benchmarks (
    benchmark_id TEXT PRIMARY KEY,
    created_at TEXT,
    kind TEXT,
    payload TEXT
);

CREATE TABLE IF NOT EXISTS live_stream_state (
    stream_id TEXT PRIMARY KEY,
    running INTEGER,
    started_at TEXT,
    ends_at TEXT,
    rate INTEGER,
    duration_seconds INTEGER,
    scenario_mix TEXT,
    transport TEXT,
    published INTEGER,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS intelligence_signals (
    intelligence_id TEXT PRIMARY KEY,
    source_institution TEXT,
    entity_type TEXT,
    entity_reference TEXT,
    signal_type TEXT,
    confidence REAL,
    pattern_id TEXT,
    sharing_tier TEXT,
    visibility TEXT,
    payload TEXT,
    created_at TEXT,
    created_by TEXT
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_txn_ts ON transactions(ts)",
    "CREATE INDEX IF NOT EXISTS idx_txn_corridor ON transactions(corridor)",
    "CREATE INDEX IF NOT EXISTS idx_txn_sender_ts ON transactions(sender_id, ts)",
    "CREATE INDEX IF NOT EXISTS idx_txn_receiver_ts ON transactions(receiver_id, ts)",
    "CREATE INDEX IF NOT EXISTS idx_txn_device_ts ON transactions(device_id, ts)",
    "CREATE INDEX IF NOT EXISTS idx_txn_benef ON transactions(beneficiary_id)",
    "CREATE INDEX IF NOT EXISTS idx_accounts_bank ON accounts(bank_id)",
    "CREATE INDEX IF NOT EXISTS idx_flagged_risk ON flagged_transactions(risk_score)",
    "CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_log(case_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts)",
    "CREATE INDEX IF NOT EXISTS idx_investigations_status ON investigations(status)",
    "CREATE INDEX IF NOT EXISTS idx_queue_status ON investigation_queue(status)",
    "CREATE INDEX IF NOT EXISTS idx_queue_status_created ON investigation_queue(status, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_pattern_matches_txn ON pattern_matches(txn_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_ingest_source_event ON ingestion_events(source_system, source_event_id) WHERE source_event_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_outbox_unpublished ON outbox_events(published_at, created_at)",
]

ACCOUNT_COLUMNS = {
    "customer_id": "TEXT",
    "bank_id": "TEXT",
    "account_type": "TEXT",
    "risk_profile": "TEXT",
}

DEVICE_COLUMNS = {
    "last_seen": "TEXT",
    "country": "TEXT",
}

BENEFICIARY_COLUMNS = {
    "bank_id": "TEXT",
    "created_at": "TEXT",
}

TRANSACTION_COLUMNS = {
    "origin_country": "TEXT",
    "destination_country": "TEXT",
    "origin_bank_id": "TEXT",
    "destination_bank_id": "TEXT",
    "channel": "TEXT",
    "risk_score": "REAL",
    "risk_tier": "TEXT",
    "status": "TEXT",
}

AUDIT_COLUMNS = {
    "role": "TEXT",
    "model_version": "TEXT",
    "pattern_version": "TEXT",
}

FLAGGED_COLUMNS = {
    "risk_tier": "TEXT",
    "network_id": "TEXT",
    "workflow_state": "TEXT",
    "showcase": "TEXT",
}

PATTERN_COLUMNS = {
    "institutional_scope": "TEXT",
}

QUEUE_COLUMNS = {
    "priority": "INTEGER",
    "attempt_count": "INTEGER",
    "claimed_at": "TEXT",
    "started_at": "TEXT",
    "completed_at": "TEXT",
    "last_error": "TEXT",
    "next_attempt_at": "TEXT",
    "worker_id": "TEXT",
}

INGEST_EVENT_COLUMNS = {
    "event_id": "TEXT",
    "source_system": "TEXT",
    "source_event_id": "TEXT",
    "event_version": "INTEGER",
    "occurred_at": "TEXT",
}


class CompatRow(dict):
    """Dict that also supports integer indexing like sqlite3.Row."""

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class CompatConnection:
    """Minimal sqlite-like facade over psycopg connections."""

    def __init__(self, raw: Any, row_factory: bool = True):
        self._raw = raw
        self._row_factory = row_factory

    def _adapt(self, sql: str) -> str:
        import re
        sql = sql.replace("?", "%s")
        return re.sub(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", r"%(\1)s", sql)

    def execute(self, sql: str, params: Sequence[Any] | dict | None = None):
        cur = self._raw.cursor()
        adapted = self._adapt(sql)
        if isinstance(params, dict):
            cur.execute(adapted, params)
        else:
            cur.execute(adapted, tuple(params or ()))
        return _PgCursor(cur, self._row_factory)

    def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any] | dict]):
        cur = self._raw.cursor()
        cur.executemany(self._adapt(sql), list(seq_of_params))
        return _PgCursor(cur, self._row_factory)

    def executescript(self, script: str) -> None:
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if not stmt:
                continue
            self._raw.cursor().execute(stmt)

    def commit(self) -> None:
        self._raw.commit()

    def close(self) -> None:
        ingest = getattr(self, "_ingest_slot", False)
        try:
            if getattr(self, "_overflow", False):
                try:
                    self._raw.close()
                finally:
                    _pg_pool_init()
                    with _PG_POOL["lock"]:
                        _PG_POOL["overflow"] = max(0, int(_PG_POOL["overflow"]) - 1)
                return
            if getattr(self, "_pooled", False):
                _release_postgres(self)
                return
            self._raw.close()
        finally:
            if ingest:
                _release_ingest_slot()

    def cursor(self):
        return _PgCursor(self._raw.cursor(), self._row_factory)


class _PgCursor:
    def __init__(self, cur: Any, row_factory: bool):
        self._cur = cur
        self._row_factory = row_factory

    def execute(self, sql: str, params: Sequence[Any] | dict | None = None):
        import re
        adapted = re.sub(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", r"%(\1)s", sql.replace("?", "%s"))
        if isinstance(params, dict):
            self._cur.execute(adapted, params)
        else:
            self._cur.execute(adapted, tuple(params or ()))
        return self

    def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any] | dict]):
        import re
        adapted = re.sub(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", r"%(\1)s", sql.replace("?", "%s"))
        self._cur.executemany(adapted, list(seq_of_params))
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        return _pg_row(row, self._cur) if row is not None else None

    def fetchall(self):
        rows = self._cur.fetchall()
        return [_pg_row(r, self._cur) for r in rows]

    def __iter__(self):
        return iter(self.fetchall())

    @property
    def lastrowid(self):
        return None

    @property
    def rowcount(self):
        return self._cur.rowcount


def _pg_row(row: Any, cur: Any) -> CompatRow:
    names = [d[0] for d in cur.description]
    if isinstance(row, dict):
        return CompatRow(row)
    return CompatRow(zip(names, row))


class DatabaseBusy(RuntimeError):
    """Raised when the Cloud SQL pool and overflow slots are exhausted."""


_PG_POOL: dict[str, Any] = {
    "lock": None,
    "idle": None,
    "size": 0,
    "max": int(os.getenv("CW_PG_POOL_MAX", "8")),
    "overflow": 0,
    "max_overflow": int(os.getenv("CW_PG_OVERFLOW", "4")),
    "ingest_sem": None,
}
_SCHEMA_READY_FOR: str | None = None


def _db_identity() -> str:
    settings = get_settings()
    if settings.is_postgres:
        return settings.database_url or "postgres"
    return str(DB_PATH)


def _pg_pool_init() -> None:
    if _PG_POOL["lock"] is None:
        import threading
        from queue import Queue
        _PG_POOL["lock"] = threading.Lock()
        _PG_POOL["idle"] = Queue()
        _PG_POOL["ingest_sem"] = threading.BoundedSemaphore(int(os.getenv("CW_INGEST_SLOTS", "8")))


def _release_ingest_slot() -> None:
    sem = _PG_POOL.get("ingest_sem")
    if sem is None:
        return
    try:
        sem.release()
    except ValueError:
        pass


def _new_postgres(row_factory: bool) -> CompatConnection:
    url = get_settings().database_url
    try:
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(url, row_factory=dict_row if row_factory else None)
        wrapped = CompatConnection(conn, row_factory=row_factory)
        wrapped._pooled = True
        return wrapped
    except ImportError:
        pass
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError as exc:
        raise RuntimeError("Install psycopg[binary] to use DATABASE_URL PostgreSQL") from exc
    parsed = urlparse(url)
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        dbname=(parsed.path or "/").lstrip("/"),
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        sslmode=os.getenv("PGSSLMODE", "prefer"),
        cursor_factory=RealDictCursor if row_factory else None,
    )
    wrapped = CompatConnection(conn, row_factory=row_factory)
    wrapped._pooled = True
    return wrapped


def _release_postgres(con: CompatConnection) -> None:
    _pg_pool_init()
    try:
        con._raw.rollback()
    except Exception:
        try:
            con._raw.close()
        except Exception:
            pass
        with _PG_POOL["lock"]:
            _PG_POOL["size"] = max(0, int(_PG_POOL["size"]) - 1)
        return
    _PG_POOL["idle"].put(con)


def _checkout_postgres(row_factory: bool, *, wait: float, allow_overflow: bool) -> CompatConnection:
    from queue import Empty
    from metrics import METRICS

    started = time.perf_counter()
    _pg_pool_init()
    idle = _PG_POOL["idle"]
    try:
        con = idle.get_nowait()
        if getattr(con, "_row_factory", True) == row_factory:
            METRICS.observe("db_connection_checkout", (time.perf_counter() - started) * 1000.0)
            return con
        _release_postgres(con)
    except Empty:
        pass
    with _PG_POOL["lock"]:
        if int(_PG_POOL["size"]) < int(_PG_POOL["max"]):
            _PG_POOL["size"] = int(_PG_POOL["size"]) + 1
            create = True
        else:
            create = False
    if create:
        con = _new_postgres(row_factory)
        METRICS.observe("db_connection_checkout", (time.perf_counter() - started) * 1000.0)
        return con
    wait_started = time.perf_counter()
    try:
        con = idle.get(timeout=wait)
        METRICS.observe("db_pool_wait", (time.perf_counter() - wait_started) * 1000.0)
        METRICS.observe("db_connection_checkout", (time.perf_counter() - started) * 1000.0)
        return con
    except Empty:
        METRICS.observe("db_pool_wait", (time.perf_counter() - wait_started) * 1000.0)
    if allow_overflow:
        with _PG_POOL["lock"]:
            if int(_PG_POOL["overflow"]) < int(_PG_POOL["max_overflow"]):
                _PG_POOL["overflow"] = int(_PG_POOL["overflow"]) + 1
                allow = True
            else:
                allow = False
        if allow:
            try:
                con = _new_postgres(row_factory)
            except Exception:
                with _PG_POOL["lock"]:
                    _PG_POOL["overflow"] = max(0, int(_PG_POOL["overflow"]) - 1)
                raise
            con._pooled = False
            con._overflow = True
            METRICS.observe("db_connection_checkout", (time.perf_counter() - started) * 1000.0)
            return con
    raise DatabaseBusy("database busy")


def _connect_postgres(row_factory: bool, purpose: str = "interactive") -> CompatConnection:
    if not row_factory:
        con = _new_postgres(False)
        con._pooled = False
        return con
    interactive = purpose != "ingest"
    if not interactive:
        _pg_pool_init()
        sem = _PG_POOL["ingest_sem"]
        wait = float(os.getenv("CW_INGEST_WAIT", "2"))
        if not sem.acquire(timeout=wait):
            raise DatabaseBusy("database busy")
        try:
            con = _checkout_postgres(row_factory, wait=wait, allow_overflow=False)
        except Exception:
            _release_ingest_slot()
            raise
        con._ingest_slot = True
        return con
    return _checkout_postgres(row_factory, wait=8.0, allow_overflow=True)


def connect(row_factory: bool = True, purpose: str = "interactive") -> sqlite3.Connection | CompatConnection:
    settings = get_settings()
    if settings.environment == "gcp" and not settings.is_postgres:
        raise RuntimeError("GCP requires DATABASE_URL PostgreSQL; SQLite is local-only")
    if settings.is_postgres:
        if purpose == "interactive" and row_factory:
            last: Exception | None = None
            for attempt in range(3):
                try:
                    return _connect_postgres(row_factory, purpose)
                except DatabaseBusy as exc:
                    last = exc
                    time.sleep(0.2 * (attempt + 1))
            raise last or DatabaseBusy("database busy")
        return _connect_postgres(row_factory, purpose)
    con = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    if row_factory:
        con.row_factory = sqlite3.Row
    return con


def pool_status() -> dict:
    """In-process pool occupancy. SQLite has no pool."""
    if not get_settings().is_postgres:
        return {"dialect": "sqlite", "utilization": 0.0, "size": 0, "max": 0, "overflow": 0}
    cap = max(1, int(_PG_POOL.get("max") or 1) + int(_PG_POOL.get("max_overflow") or 0))
    used = int(_PG_POOL.get("size") or 0) + int(_PG_POOL.get("overflow") or 0)
    return {
        "dialect": "postgres",
        "size": int(_PG_POOL.get("size") or 0),
        "max": int(_PG_POOL.get("max") or 0),
        "overflow": int(_PG_POOL.get("overflow") or 0),
        "max_overflow": int(_PG_POOL.get("max_overflow") or 0),
        "utilization": round(used / cap, 4),
    }


def warmup_pool() -> int:
    """Open the ingest pool so the first Pub/Sub burst does not 503."""
    if not get_settings().is_postgres:
        return 0
    n = max(1, int(_PG_POOL.get("max") or int(os.getenv("CW_PG_POOL_MAX", "8"))))
    held = []
    try:
        for _ in range(n):
            held.append(connect(purpose="ingest"))
    finally:
        for con in held:
            try:
                con.close()
            except Exception:
                pass
    return len(held)


def dialect() -> str:
    return get_settings().dialect


def insert_or_ignore(con: Any, table: str, columns: Sequence[str], values: Sequence[Any], conflict: str) -> bool:
    """Idempotent insert. PostgreSQL uses ON CONFLICT; SQLite uses INSERT OR IGNORE."""
    cols = ", ".join(columns)
    placeholders = ", ".join("?" * len(columns))
    if get_settings().is_postgres:
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT ({conflict}) DO NOTHING"
    else:
        sql = f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})"
    cur = con.execute(sql, values)
    count = getattr(cur, "rowcount", 0)
    if callable(count):
        count = count()
    return int(count or 0) > 0


def insert_many_or_ignore(con: Any, table: str, columns: Sequence[str], rows: Sequence[Sequence[Any]], conflict: str) -> None:
    if not rows:
        return
    cols = ", ".join(columns)
    one = "(" + ", ".join("?" * len(columns)) + ")"
    values_sql = ", ".join(one for _ in rows)
    flat = [v for row in rows for v in row]
    if get_settings().is_postgres:
        sql = f"INSERT INTO {table} ({cols}) VALUES {values_sql} ON CONFLICT ({conflict}) DO NOTHING"
    else:
        sql = f"INSERT OR IGNORE INTO {table} ({cols}) VALUES {values_sql}"
    con.execute(sql, flat)


def upsert(con: Any, table: str, pk: str | Sequence[str], data: dict[str, Any]) -> None:
    """Portable insert-or-replace for SQLite and PostgreSQL."""
    keys = list(data.keys())
    values = [data[k] for k in keys]
    cols = ", ".join(keys)
    placeholders = ", ".join("?" * len(keys))
    pk_cols = (pk,) if isinstance(pk, str) else tuple(pk)
    if get_settings().is_postgres:
        assignments = ", ".join(f"{k}=EXCLUDED.{k}" for k in keys if k not in pk_cols)
        conflict = ", ".join(pk_cols)
        sql = (
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict}) DO UPDATE SET {assignments}"
        )
        con.execute(sql, values)
        return
    sql = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"
    con.execute(sql, values)


def _table_columns(con: Any, table: str) -> set[str]:
    if get_settings().is_postgres:
        rows = con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name=?",
            (table,),
        ).fetchall()
        return {r["column_name"] if isinstance(r, dict) else r[0] for r in rows}
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] if not isinstance(r, tuple) else r[1] for r in rows}


def _ensure_columns(con: Any, table: str, columns: dict[str, str]) -> None:
    try:
        existing = _table_columns(con, table)
    except Exception:
        return
    for name, typedef in columns.items():
        if name in existing:
            continue
        try:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typedef}")
        except Exception:
            pass


def _create_indexes(con: Any) -> None:
    for stmt in INDEXES:
        try:
            con.execute(stmt)
        except Exception:
            pass


def init_schema(con: sqlite3.Connection | CompatConnection | None = None) -> None:
    global _SCHEMA_READY_FOR
    own = con is None
    ident = _db_identity()
    if own and _SCHEMA_READY_FOR == ident:
        return
    if own:
        con = connect(row_factory=False)
    schema = SCHEMA
    if get_settings().is_postgres:
        schema = SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    con.executescript(schema)
    con.executescript(PLATFORM_SCHEMA)
    _ensure_columns(con, "accounts", ACCOUNT_COLUMNS)
    _ensure_columns(con, "devices", DEVICE_COLUMNS)
    _ensure_columns(con, "beneficiaries", BENEFICIARY_COLUMNS)
    _ensure_columns(con, "transactions", TRANSACTION_COLUMNS)
    _ensure_columns(con, "audit_log", AUDIT_COLUMNS)
    _ensure_columns(con, "flagged_transactions", FLAGGED_COLUMNS)
    _ensure_columns(con, "investigation_queue", QUEUE_COLUMNS)
    _ensure_columns(con, "ingestion_events", INGEST_EVENT_COLUMNS)
    _ensure_columns(con, "crime_patterns", PATTERN_COLUMNS)
    _create_indexes(con)
    con.commit()
    _SCHEMA_READY_FOR = ident
    if own:
        con.close()
