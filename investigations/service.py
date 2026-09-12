"""Investigation pipeline — graph + DNA + optional Gemini. Not used on ingest."""
from __future__ import annotations

import json

from config import get_settings
from db import connect, init_schema, upsert
from graph.investigator import bounded_network
from investigations.evidence import build_evidence_items, deterministic_report
from investigations.schemas import InvestigationReport
from metrics import METRICS
from patterns.matcher import match_patterns
from pubsub.schemas import utc_now
from risk.tiers import RiskTier, assign_tier


def load_txn(txn_id: str) -> dict:
    con = connect()
    row = con.execute("SELECT * FROM flagged_transactions WHERE txn_id=?", (txn_id,)).fetchone()
    if not row:
        row = con.execute("SELECT * FROM transactions WHERE txn_id=?", (txn_id,)).fetchone()
    con.close()
    if not row:
        raise ValueError(f"transaction {txn_id} not found")
    return dict(row)


def load_risk(account_id: str) -> dict:
    con = connect()
    row = con.execute("SELECT * FROM risk_scores WHERE account_id=?", (account_id,)).fetchone()
    con.close()
    return dict(row) if row else {}


def build_investigation(txn_id: str, *, use_gemini: bool = False) -> dict:
    init_schema()
    txn = load_txn(txn_id)
    risk = load_risk(txn.get("sender_id") or "") or load_risk(txn.get("receiver_id") or "")
    network = bounded_network(txn)
    matches = match_patterns(txn, network, risk)
    evidence = build_evidence_items(txn, network, risk, matches)
    report = deterministic_report(txn, evidence, matches, risk, network)
    gemini_error = None
    if use_gemini:
        try:
            from agent import grounded_gemini_report
            report = grounded_gemini_report(txn, evidence, matches, risk, network, report)
        except Exception as exc:
            gemini_error = str(exc)
            METRICS.inc("gemini_failures_total")
            report.uncertainty = f"Gemini unavailable ({exc}). Deterministic grounded report retained."

    _persist_case(txn, network, report, matches)
    METRICS.inc("investigations_completed_total")
    return {
        "txn_id": txn_id,
        "network": network,
        "pattern_matches": matches,
        "evidence": [e.model_dump() for e in evidence],
        "report": report.model_dump(),
        "risk_tier": (txn.get("risk_tier") or assign_tier(float(txn.get("risk_score") or 0)).value),
        "gemini_error": gemini_error,
    }


def process_queue_item(queue_id: str | None = None, txn_id: str | None = None) -> dict:
    """Process one pending investigation. HIGH/CRITICAL may request Gemini; ingest already finished."""
    init_schema()
    con = connect()
    if queue_id:
        row = con.execute("SELECT * FROM investigation_queue WHERE queue_id=?", (queue_id,)).fetchone()
    elif txn_id:
        row = con.execute(
            "SELECT * FROM investigation_queue WHERE txn_id=? ORDER BY created_at DESC LIMIT 1",
            (txn_id,),
        ).fetchone()
    else:
        row = con.execute(
            "SELECT * FROM investigation_queue WHERE status='pending' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
    if not row:
        con.close()
        return {"status": "empty"}
    item = dict(row)
    con.execute(
        "UPDATE investigation_queue SET status=?, updated_at=? WHERE queue_id=?",
        ("running", utc_now(), item["queue_id"]),
    )
    con.commit()
    con.close()

    settings = get_settings()
    tier = item.get("risk_tier") or "MEDIUM"
    use_gemini = False
    if tier in {RiskTier.HIGH.value, RiskTier.CRITICAL.value}:
        try:
            import agent
            use_gemini = agent.gemini_available()
        except Exception:
            use_gemini = False
    result = build_investigation(item["txn_id"], use_gemini=use_gemini)
    con = connect()
    con.execute(
        "UPDATE investigation_queue SET status=?, updated_at=? WHERE queue_id=?",
        ("complete", utc_now(), item["queue_id"]),
    )
    con.commit()
    con.close()
    result["queue_id"] = item["queue_id"]
    result["settings_note"] = (
        f"Gemini invoked only for HIGH/CRITICAL. Current tier={tier}. "
        f"model={settings.gemini_model}"
    )
    return result


def _persist_case(txn: dict, network: dict, report: InvestigationReport, matches: list[dict]) -> None:
    con = connect(row_factory=False)
    upsert(con, "investigations", "case_id", {
        "case_id": txn["txn_id"],
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": "pending_review",
        "risk_level": report.recommended_disposition,
        "primary_txn_id": txn["txn_id"],
        "network_id": network.get("network_id"),
        "pattern_ids": json.dumps([m["pattern_id"] for m in matches]),
        "ai_summary": report.investigation_summary,
        "ai_hypothesis": report.risk_hypothesis,
        "confidence": report.confidence,
        "analyst_decision": "",
        "assigned_role": "analyst" if report.recommended_disposition in {"clear", "monitor"} else "fiu_lead",
    })
    con.commit()
    con.close()
