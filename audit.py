"""Append-only audit trail for investigations, tool calls, verdicts, decisions."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from db import connect, init_schema


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_authz(
    case_id: str,
    *,
    actor: str,
    role: str,
    action: str,
    old_state: str = "",
    new_state: str = "",
    reason: str = "",
    source_ip: str = "",
    evidence_snapshot: str | None = None,
) -> None:
    log(
        case_id,
        "authorization",
        {
            "who": actor,
            "what": action,
            "when": _now(),
            "case": case_id,
            "old_state": old_state,
            "new_state": new_state,
            "reason": reason,
            "ip": source_ip,
            "recommendation_id": evidence_snapshot,
            "evidence_snapshot": evidence_snapshot,
        },
        actor=actor,
        role=role,
    )


def log(
    case_id: str,
    event_type: str,
    detail,
    actor: str = "system",
    *,
    role: str | None = None,
    model_version: str | None = None,
    pattern_version: str | None = None,
) -> None:
    init_schema()
    con = None
    try:
        con = connect()
        if not isinstance(detail, str):
            payload = dict(detail) if isinstance(detail, dict) else {"value": detail}
            if role:
                payload.setdefault("role", role)
            if model_version:
                payload.setdefault("model_version", model_version)
            if pattern_version:
                payload.setdefault("pattern_version", pattern_version)
            try:
                from tracing import current
                tid = current().get("trace_id")
                if tid:
                    payload.setdefault("trace_id", tid)
            except Exception:
                pass
            detail = json.dumps(payload, default=str)
        try:
            con.execute(
                "INSERT INTO audit_log (ts, case_id, actor, event_type, detail, role, model_version, pattern_version) VALUES (?,?,?,?,?,?,?,?)",
                (_now(), case_id, actor, event_type, detail, role, model_version, pattern_version),
            )
        except Exception:
            con.execute(
                "INSERT INTO audit_log (ts, case_id, actor, event_type, detail) VALUES (?,?,?,?,?)",
                (_now(), case_id, actor, event_type, detail),
            )
        con.commit()
    except Exception:
        pass
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass


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
