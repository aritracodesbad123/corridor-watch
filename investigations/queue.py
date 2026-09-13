"""Durable investigation queue. PostgreSQL is authoritative; Pub/Sub is notify-only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db import connect, init_schema
from pubsub.schemas import utc_now

# After claim N fails: delay then DLQ on the 5th attempt.
BACKOFF_SECONDS = (0, 1, 5, 30, 300)
MAX_ATTEMPTS = 5

ACTIVE = ("QUEUED", "CLAIMED", "RUNNING", "RETRY", "pending")
CLAIMABLE = ("QUEUED", "RETRY", "pending")


def enqueue(con, queue_id: str, txn_id: str, network_id: str, risk_tier: str, *, priority: int = 0) -> None:
    now = utc_now()
    con.execute(
        """INSERT INTO investigation_queue
           (queue_id, txn_id, network_id, risk_tier, status, created_at, updated_at,
            priority, attempt_count)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (queue_id, txn_id, network_id, risk_tier, "QUEUED", now, now, priority, 0),
    )


def claim_next(worker_id: str, limit: int = 1) -> list[dict]:
    """Claim queued jobs. Postgres uses SKIP LOCKED; SQLite updates one row at a time."""
    init_schema()
    con = connect()
    now = utc_now()
    claimed: list[dict] = []
    try:
        from config import get_settings
        if get_settings().is_postgres:
            rows = con.execute(
                """SELECT queue_id FROM investigation_queue
                   WHERE status IN ('QUEUED','RETRY','pending')
                     AND (next_attempt_at IS NULL OR next_attempt_at<=?)
                   ORDER BY COALESCE(priority,0) DESC, created_at
                   FOR UPDATE SKIP LOCKED
                   LIMIT ?""",
                (now, limit),
            ).fetchall()
        else:
            rows = con.execute(
                """SELECT queue_id FROM investigation_queue
                   WHERE status IN ('QUEUED','RETRY','pending')
                     AND (next_attempt_at IS NULL OR next_attempt_at<=?)
                   ORDER BY COALESCE(priority,0) DESC, created_at
                   LIMIT ?""",
                (now, limit),
            ).fetchall()
        for row in rows:
            qid = row["queue_id"]
            con.execute(
                """UPDATE investigation_queue
                   SET status='CLAIMED', worker_id=?, claimed_at=?, updated_at=?,
                       attempt_count=COALESCE(attempt_count,0)+1
                   WHERE queue_id=? AND status IN ('QUEUED','RETRY','pending')""",
                (worker_id, now, now, qid),
            )
            fresh = con.execute("SELECT * FROM investigation_queue WHERE queue_id=?", (qid,)).fetchone()
            if fresh and fresh["status"] == "CLAIMED":
                claimed.append(dict(fresh))
        con.commit()
    finally:
        con.close()
    return claimed


def mark_running(queue_id: str, worker_id: str) -> None:
    now = utc_now()
    con = connect()
    con.execute(
        """UPDATE investigation_queue
           SET status='RUNNING', worker_id=?, started_at=COALESCE(started_at, ?), updated_at=?
           WHERE queue_id=?""",
        (worker_id, now, now, queue_id),
    )
    con.commit()
    con.close()


def mark_completed(queue_id: str) -> None:
    now = utc_now()
    con = connect()
    con.execute(
        """UPDATE investigation_queue
           SET status='COMPLETED', completed_at=?, updated_at=?, last_error=NULL
           WHERE queue_id=?""",
        (now, now, queue_id),
    )
    con.commit()
    con.close()


def mark_failed(queue_id: str, error: str, *, retry: bool = True, max_attempts: int = MAX_ATTEMPTS) -> str:
    con = connect()
    row = con.execute("SELECT attempt_count FROM investigation_queue WHERE queue_id=?", (queue_id,)).fetchone()
    attempts = int((row["attempt_count"] if row and row["attempt_count"] is not None else 1))
    now = utc_now()
    if retry and attempts < max_attempts:
        status = "RETRY"
        delay = BACKOFF_SECONDS[min(attempts - 1, len(BACKOFF_SECONDS) - 1)]
        nxt = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
        con.execute(
            """UPDATE investigation_queue
               SET status=?, last_error=?, next_attempt_at=?, updated_at=?, worker_id=NULL
               WHERE queue_id=?""",
            (status, error[:500], nxt, now, queue_id),
        )
    else:
        status = "DEAD_LETTER"
        con.execute(
            """UPDATE investigation_queue
               SET status=?, last_error=?, updated_at=?
               WHERE queue_id=?""",
            (status, error[:500], now, queue_id),
        )
    con.commit()
    con.close()
    return status


def _set(queue_id: str, status: str, worker_id: str | None = None) -> None:
    now = utc_now()
    con = connect()
    if worker_id:
        con.execute(
            "UPDATE investigation_queue SET status=?, worker_id=?, updated_at=? WHERE queue_id=?",
            (status, worker_id, now, queue_id),
        )
    else:
        con.execute(
            "UPDATE investigation_queue SET status=?, updated_at=? WHERE queue_id=?",
            (status, now, queue_id),
        )
    con.commit()
    con.close()


def counts() -> dict[str, int]:
    init_schema()
    con = connect()
    rows = con.execute("SELECT status, COUNT(*) AS c FROM investigation_queue GROUP BY status").fetchall()
    con.close()
    out = {str(r["status"]): int(r["c"]) for r in rows}
    out["active"] = sum(out.get(s, 0) for s in ACTIVE)
    return out
