"""Analyst → FIU Lead → MRM audit case states."""
from __future__ import annotations

from datetime import datetime, timezone

from db import connect, init_schema
import audit

STATES = ("open", "analyst_review", "referred_fiu", "escalated_fiu", "closed")

ACTIONS = {
    "start_review": {"next": "analyst_review", "roles": {"analyst", "fiu_lead"}},
    "refer_fiu": {"next": "referred_fiu", "roles": {"analyst"}},
    "escalate": {"next": "escalated_fiu", "roles": {"fiu_lead"}},
    "close": {"next": "closed", "roles": {"fiu_lead", "mrm_auditor"}},
    "audit_ack": {"next": "closed", "roles": {"mrm_auditor"}},
}

ANALYST_QUEUE = {"open", "analyst_review"}
FIU_QUEUE = {"referred_fiu", "escalated_fiu"}
MRM_QUEUE = {"referred_fiu", "escalated_fiu", "closed"}


def visible_to_role(row: dict, role: str) -> bool:
    if row.get("showcase"):
        return True
    state = row.get("workflow_state") or "open"
    if role == "analyst":
        return state in ANALYST_QUEUE
    if role == "fiu_lead":
        return state in FIU_QUEUE
    if role == "mrm_auditor":
        return state in MRM_QUEUE
    return True

DECISION_STATE = {
    "clear": "closed",
    "monitor": "analyst_review",
    "hold_payment": "escalated_fiu",
    "escalate_fiu": "escalated_fiu",
    "freeze_account": "escalated_fiu",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_for(txn_id: str) -> str:
    init_schema()
    con = connect()
    row = con.execute(
        "SELECT workflow_state FROM flagged_transactions WHERE txn_id=?",
        (txn_id,),
    ).fetchone()
    con.close()
    if not row:
        raise ValueError("alert not found")
    return row["workflow_state"] or "open"


def set_state(txn_id: str, state: str, *, actor: str, role: str, notes: str = "", action: str = "") -> dict:
    if state not in STATES:
        raise ValueError(f"unknown workflow state {state}")
    init_schema()
    con = connect()
    current = con.execute(
        "SELECT workflow_state FROM flagged_transactions WHERE txn_id=?", (txn_id,)
    ).fetchone()
    if not current:
        con.close()
        raise ValueError("alert not found")
    old_state = current["workflow_state"] or "open"
    con.execute(
        "UPDATE flagged_transactions SET workflow_state=? WHERE txn_id=?",
        (state, txn_id),
    )
    try:
        con.execute(
            "UPDATE investigations SET status=?, updated_at=?, assigned_role=? WHERE case_id=?",
            (state, _now(), role, txn_id),
        )
    except Exception:
        pass
    con.commit()
    con.close()
    audit.log_authz(
        txn_id,
        actor=actor,
        role=role,
        action=action or state,
        old_state=old_state,
        new_state=state,
        reason=notes,
    )
    return {"txn_id": txn_id, "workflow_state": state, "action": action or state, "notes": notes}


def apply_action(txn_id: str, action: str, *, actor: str, role: str, notes: str = "") -> dict:
    spec = ACTIONS.get(action)
    if not spec:
        raise ValueError(f"unknown workflow action {action}")
    if role not in spec["roles"]:
        raise PermissionError(f"role '{role}' cannot {action}")
    return set_state(txn_id, spec["next"], actor=actor, role=role, notes=notes, action=action)


def apply_decision(txn_id: str, decision: str, *, actor: str, role: str, notes: str = "") -> dict:
    nxt = DECISION_STATE.get(decision)
    if not nxt:
        return {"txn_id": txn_id, "workflow_state": state_for(txn_id)}
    return set_state(txn_id, nxt, actor=actor, role=role, notes=notes, action=decision)


def queue(limit: int = 80) -> list[dict]:
    init_schema()
    con = connect()
    rows = con.execute(
        "SELECT txn_id, corridor, amount, risk_score, primary_pattern, workflow_state, "
        "network_id, showcase, sender_id, receiver_id FROM flagged_transactions "
        "ORDER BY CASE WHEN showcase IS NOT NULL AND showcase != '' THEN 0 ELSE 1 END, "
        "risk_score DESC LIMIT ?",
        (limit,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def counts() -> dict:
    init_schema()
    con = connect()
    rows = con.execute(
        "SELECT COALESCE(workflow_state, 'open') AS workflow_state, COUNT(*) AS c "
        "FROM flagged_transactions GROUP BY COALESCE(workflow_state, 'open')"
    ).fetchall()
    con.close()
    out = {s: 0 for s in STATES}
    for r in rows:
        key = r["workflow_state"] or "open"
        out[key] = int(r["c"])
    return out
