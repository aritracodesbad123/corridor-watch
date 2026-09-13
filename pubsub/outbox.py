"""Transactional outbox. Publish happens after COMMIT; unpublished rows retry."""
from __future__ import annotations

import json
import time
import uuid

from db import connect, init_schema, insert_or_ignore
from metrics import METRICS
from pubsub.schemas import utc_now


def enqueue(con, *, event_type: str, payload: dict) -> str:
    outbox_id = f"OB-{uuid.uuid4().hex[:12]}"
    insert_or_ignore(
        con,
        "outbox_events",
        ("outbox_id", "event_type", "payload", "created_at", "published_at", "attempts", "last_error"),
        (outbox_id, event_type, json.dumps(payload), utc_now(), None, 0, None),
        "outbox_id",
    )
    return outbox_id


def drain(limit: int = 20) -> int:
    """Publish unpublished rows. Safe after the ingest commit."""
    init_schema()
    con = connect()
    rows = [dict(r) for r in con.execute(
        """SELECT * FROM outbox_events
           WHERE published_at IS NULL
           ORDER BY created_at
           LIMIT ?""",
        (limit,),
    ).fetchall()]
    con.close()
    sent = 0
    for row in rows:
        if _publish_one(row):
            sent += 1
    return sent


def _publish_one(row: dict) -> bool:
    from pubsub.publisher import notify_investigation
    payload = json.loads(row.get("payload") or "{}")
    try:
        notify_investigation(payload)
    except Exception as exc:
        _mark(row["outbox_id"], published=False, error=str(exc))
        METRICS.inc("outbox_publish_failed_total")
        return False
    _mark(row["outbox_id"], published=True)
    METRICS.inc("outbox_published_total")
    return True


def _mark(outbox_id: str, *, published: bool, error: str = "") -> None:
    con = connect()
    if published:
        con.execute(
            "UPDATE outbox_events SET published_at=?, attempts=COALESCE(attempts,0)+1, last_error=NULL WHERE outbox_id=?",
            (utc_now(), outbox_id),
        )
    else:
        con.execute(
            "UPDATE outbox_events SET attempts=COALESCE(attempts,0)+1, last_error=? WHERE outbox_id=?",
            (error[:500], outbox_id),
        )
    con.commit()
    con.close()


def run_worker(*, idle_seconds: float = 1.0) -> None:
    """CW_ROLE=outbox. Durable fan-out only."""
    while True:
        if drain() == 0:
            time.sleep(idle_seconds)
