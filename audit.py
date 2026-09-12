"""Append-only audit trail for investigations, tool calls, verdicts, decisions."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from db import connect, init_schema


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(case_id: str, event_type: str, detail, actor: str = "system") -> None:
    init_schema()
    con = connect(row_factory=False)
    if not isinstance(detail, str):
        detail = json.dumps(detail, default=str)
    con.execute(
        "INSERT INTO audit_log (ts, case_id, actor, event_type, detail) VALUES (?,?,?,?,?)",
        (_now(), case_id, actor, event_type, detail),
    )
    con.commit()
    con.close()


def list_for_case(case_id: str, limit: int = 200) -> list[dict]:
    init_schema()
    con = connect()
    rows = con.execute(
        "SELECT * FROM audit_log WHERE case_id=? ORDER BY id ASC LIMIT ?",
        (case_id, limit),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def list_recent(limit: int = 100) -> list[dict]:
    init_schema()
    con = connect()
    rows = con.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]
