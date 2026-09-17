"""
12-step deterministic investigation DAG.

Every step gathers evidence, logs to the audit trail, and feeds the next step.
Fully auditable without an LLM; Gemini/agent mode consumes the same evidence pack.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from db import connect, init_schema, upsert
import audit

STEPS: list[tuple[str, str]] = [
    ("load_transaction", "Load flagged transaction record"),
    ("load_sender_profile", "Fetch sender KYC / profile"),
    ("load_receiver_profile", "Fetch receiver KYC / profile"),
    ("load_risk_features", "Load graph risk features for both parties"),
    ("load_session_biometrics", "Pull session behavioral biometrics"),
    ("load_shared_devices", "Enumerate shared devices across counterparties"),
    ("load_shared_beneficiaries", "Enumerate shared beneficiaries"),
    ("compute_network_neighborhood", "Build 1-hop transaction neighborhood"),
    ("check_corridor_velocity", "Assess corridor velocity / burstiness"),
    ("score_named_patterns", "Score named fraud patterns"),
    ("assemble_evidence_pack", "Assemble structured evidence pack"),
    ("draft_deterministic_verdict", "Produce deterministic verdict from evidence"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _account(con, account_id: str) -> dict:
    row = con.execute("SELECT * FROM accounts WHERE account_id=?", (account_id,)).fetchone()
    return dict(row) if row else {"account_id": account_id, "note": "external/unregistered"}


def _risk(con, account_id: str) -> dict:
    row = con.execute("SELECT * FROM risk_scores WHERE account_id=?", (account_id,)).fetchone()
    if not row:
        return {}
    d = dict(row)
    if d.get("pattern_scores"):
        try:
            d["pattern_scores"] = json.loads(d["pattern_scores"])
        except json.JSONDecodeError:
            pass
    return d


def _sessions(con, account_id: str) -> list[dict]:
    rows = con.execute(
        "SELECT * FROM sessions WHERE account_id=? ORDER BY started_at DESC LIMIT 5",
        (account_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _shared_devices(con, account_id: str) -> list[dict]:
    rows = con.execute(
        """SELECT ad.device_id, d.fingerprint, d.os, ad2.account_id AS peer_account
           FROM account_devices ad
           JOIN devices d ON d.device_id = ad.device_id
           JOIN account_devices ad2 ON ad2.device_id = ad.device_id
           WHERE ad.account_id=? AND ad2.account_id != ?
           LIMIT 20""",
        (account_id, account_id),
    ).fetchall()
    return [dict(r) for r in rows]


def _shared_beneficiaries(con, account_id: str) -> list[dict]:
    rows = con.execute(
        """SELECT ab.beneficiary_id, b.name, b.country, ab2.account_id AS peer_account
           FROM account_beneficiaries ab
           JOIN beneficiaries b ON b.beneficiary_id = ab.beneficiary_id
           JOIN account_beneficiaries ab2 ON ab2.beneficiary_id = ab.beneficiary_id
           WHERE ab.account_id=? AND ab2.account_id != ?
           LIMIT 20""",
        (account_id, account_id),
    ).fetchall()
    return [dict(r) for r in rows]


def _neighborhood(con, sender_id: str, receiver_id: str) -> list[dict]:
    rows = con.execute(
        """SELECT txn_id, sender_id, receiver_id, amount, corridor, ts
           FROM transactions
           WHERE sender_id IN (?,?) OR receiver_id IN (?,?)
           ORDER BY ts DESC LIMIT 25""",
        (sender_id, receiver_id, sender_id, receiver_id),
    ).fetchall()
    return [dict(r) for r in rows]


def deterministic_verdict(evidence: dict) -> dict:
    """Rule-based verdict — always available without an LLM."""
    sender_risk = evidence.get("sender_risk") or {}
    receiver_risk = evidence.get("receiver_risk") or {}
    txn = evidence.get("transaction") or {}
    s_score = float(sender_risk.get("risk_score") or 0)
    r_score = float(receiver_risk.get("risk_score") or 0)
    winner = sender_risk if s_score >= r_score else receiver_risk
    primary = winner.get("primary_pattern") or txn.get("primary_pattern") or "elevated_activity"
    score = max(s_score, r_score, float(txn.get("risk_score") or 0))
    if score >= 75:
        level = "high"
    elif score >= 50:
        level = "medium"
    else:
        level = "low"

    hold = min(
        float(sender_risk.get("avg_hold_time_minutes") or 99999),
        float(receiver_risk.get("avg_hold_time_minutes") or 99999),
    )
    shared_dev = max(
        int(sender_risk.get("shared_device_count") or 0),
        int(receiver_risk.get("shared_device_count") or 0),
    )
    fan_in = max(
        int(sender_risk.get("fan_in_count") or 0),
        int(receiver_risk.get("fan_in_count") or 0),
    )
    ptr = max(
        float(sender_risk.get("pass_through_ratio") or 0),
        float(receiver_risk.get("pass_through_ratio") or 0),
    )
    beh = max(
        float(sender_risk.get("behavioral_risk") or 0),
        float(receiver_risk.get("behavioral_risk") or 0),
    )

    pattern_plain = {
        "mule_pass_through": "money in and out almost immediately (pass-through)",
        "split_transaction_laundering": "one large amount split into many smaller wires",
        "shared_device_ring": "several accounts controlled from the same device",
        "synthetic_identity": "identity details that look fabricated or inconsistent",
        "multi_hop_chain": "funds hopping across several accounts before exit",
        "elevated_activity": "unusually busy activity for this corridor",
    }.get(str(primary), str(primary).replace("_", " "))

    rationale_bits = [
        f"Automated review scored this case {score:.0f}/100 ({level} risk).",
        f"Main pattern flagged: {pattern_plain}.",
    ]
    if fan_in:
        rationale_bits.append(f"About {fan_in} inbound counterparties feed into the watch account.")
    if ptr >= 0.5:
        rationale_bits.append(
            f"Roughly {ptr:.0%} of money that arrives leaves again quickly (pass-through)."
        )
    if hold < 99999:
        rationale_bits.append(f"Typical hold before the next payout is about {hold:.0f} minutes.")
    if shared_dev:
        rationale_bits.append(f"{shared_dev} accounts appear to share a device fingerprint.")
    if beh:
        rationale_bits.append(f"Behavioral risk overlay is {beh:.0f}.")
    if evidence.get("shared_devices"):
        rationale_bits.append(
            f"Shared-device peers observed in the evidence pack: {len(evidence['shared_devices'])}."
        )
    if evidence.get("sender_sessions") or evidence.get("receiver_sessions"):
        rationale_bits.append("Login/session signals were included in the evidence pack.")

    actions = {
        "high": "Pause this payment and send it to an FIU lead for a human decision (do not clear on automation alone).",
        "medium": "Ask the analyst to collect purpose / source-of-funds documents and watch related corridor activity for 72 hours.",
        "low": "Document why this looks ordinary, clear with a short note, and keep a light watch for 30 days.",
    }
    return {
        "risk_level": level,
        "risk_score": int(round(score)),
        "primary_pattern": primary,
        "rationale": " ".join(rationale_bits),
        "recommended_action": actions[level],
        "evidence_refs": [
            "sender_risk", "receiver_risk", "shared_devices",
            "shared_beneficiaries", "neighborhood", "sessions",
        ],
        "mode": "deterministic",
        "pattern_scores": winner.get("pattern_scores") or {},
    }


def run_dag(txn_id: str, *, audit_events: bool = True) -> dict[str, Any]:
    """Execute all 12 steps; return evidence + deterministic verdict + trace."""
    init_schema()
    run_id = str(uuid.uuid4())[:12]
    con = connect()
    trace: list[dict] = []
    evidence: dict[str, Any] = {"run_id": run_id, "txn_id": txn_id}

    def step(name: str, description: str, fn: Callable[[], Any]):
        started = _now()
        if audit_events:
            audit.log(txn_id, "dag_step_start", {"step": name, "description": description}, actor="dag")
        try:
            result = fn()
            entry = {"step": name, "description": description, "status": "ok",
                     "started_at": started, "finished_at": _now()}
            trace.append(entry)
            if audit_events:
                audit.log(txn_id, "dag_step_complete", {"step": name, "preview": _preview(result)}, actor="dag")
            return result
        except Exception as e:
            entry = {"step": name, "description": description, "status": "error",
                     "error": str(e), "started_at": started, "finished_at": _now()}
            trace.append(entry)
            if audit_events:
                audit.log(txn_id, "dag_step_error", {"step": name, "error": str(e)}, actor="dag")
            raise

    def _preview(obj) -> Any:
        if isinstance(obj, dict):
            return {k: (v if not isinstance(v, (list, dict)) else type(v).__name__) for k, v in list(obj.items())[:12]}
        if isinstance(obj, list):
            return {"count": len(obj)}
        return str(obj)[:200]

    txn_row = step("load_transaction", STEPS[0][1], lambda: dict(
        con.execute("SELECT * FROM flagged_transactions WHERE txn_id=?", (txn_id,)).fetchone()
        or con.execute("SELECT * FROM transactions WHERE txn_id=?", (txn_id,)).fetchone()
        or {}
    ))
    if not txn_row:
        con.close()
        raise ValueError(f"transaction {txn_id} not found")
    evidence["transaction"] = txn_row
    sender_id = txn_row["sender_id"]
    receiver_id = txn_row["receiver_id"]

    evidence["sender_profile"] = step("load_sender_profile", STEPS[1][1], lambda: _account(con, sender_id))
    evidence["receiver_profile"] = step("load_receiver_profile", STEPS[2][1], lambda: _account(con, receiver_id))
    evidence["sender_risk"] = step("load_risk_features", STEPS[3][1], lambda: _risk(con, sender_id))
    # also load receiver risk in same conceptual step
    evidence["receiver_risk"] = _risk(con, receiver_id)
    audit.log(txn_id, "dag_step_complete", {"step": "load_risk_features_receiver", "ok": True}, actor="dag")

    evidence["sender_sessions"] = step(
        "load_session_biometrics", STEPS[4][1],
        lambda: {"sender": _sessions(con, sender_id), "receiver": _sessions(con, receiver_id)},
    )
    evidence["receiver_sessions"] = evidence["sender_sessions"].get("receiver", [])
    evidence["sender_sessions"] = evidence["sender_sessions"].get("sender", [])

    evidence["shared_devices"] = step(
        "load_shared_devices", STEPS[5][1],
        lambda: _shared_devices(con, sender_id) + _shared_devices(con, receiver_id),
    )
    evidence["shared_beneficiaries"] = step(
        "load_shared_beneficiaries", STEPS[6][1],
        lambda: _shared_beneficiaries(con, sender_id) + _shared_beneficiaries(con, receiver_id),
    )
    evidence["neighborhood"] = step(
        "compute_network_neighborhood", STEPS[7][1],
        lambda: _neighborhood(con, sender_id, receiver_id),
    )
    evidence["corridor_velocity"] = step(
        "check_corridor_velocity", STEPS[8][1],
        lambda: {
            "sender": (evidence["sender_risk"] or {}).get("corridor_velocity_score", 0),
            "receiver": (evidence["receiver_risk"] or {}).get("corridor_velocity_score", 0),
            "corridor": txn_row.get("corridor"),
        },
    )
    evidence["named_patterns"] = step(
        "score_named_patterns", STEPS[9][1],
        lambda: {
            "sender": (evidence["sender_risk"] or {}).get("pattern_scores") or {},
            "receiver": (evidence["receiver_risk"] or {}).get("pattern_scores") or {},
            "txn_pattern": txn_row.get("primary_pattern"),
        },
    )
    evidence_pack = step(
        "assemble_evidence_pack", STEPS[10][1],
        lambda: {
            "txn_id": txn_id,
            "amount": txn_row.get("amount"),
            "corridor": txn_row.get("corridor"),
            "purpose": txn_row.get("purpose"),
            "source_of_funds": txn_row.get("source_of_funds"),
            "keys": list(evidence.keys()),
        },
    )
    evidence["evidence_pack"] = evidence_pack
    verdict = step("draft_deterministic_verdict", STEPS[11][1], lambda: deterministic_verdict(evidence))
    evidence["deterministic_verdict"] = verdict

    upsert(con, "investigation_runs", "run_id", {
        "run_id": run_id,
        "txn_id": txn_id,
        "started_at": trace[0]["started_at"] if trace else _now(),
        "finished_at": _now(),
        "mode": "deterministic_dag",
        "status": "complete",
        "dag_trace": json.dumps(trace),
        "verdict": json.dumps(verdict),
    })
    con.commit()
    con.close()
    if audit_events:
        audit.log(txn_id, "dag_complete", {"run_id": run_id, "verdict": verdict}, actor="dag")
    return {"run_id": run_id, "trace": trace, "evidence": evidence, "verdict": verdict}


def step_catalog() -> list[dict]:
    return [{"id": i + 1, "name": n, "description": d} for i, (n, d) in enumerate(STEPS)]
