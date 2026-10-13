"""Seed deterministic Gemini-shaped verdicts for demo replay (CW_DEMO_REPLAY=1)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from db import connect, upsert


def _gate_fail_brief_for_mid03() -> dict:
    """Run the real output gate on an invented bank-owner claim; store the gated result."""
    from agent import apply_grounding_gate
    from investigations.schemas import EvidenceItem, InvestigationReport

    allowed = {"E-TXN"}
    fallback = InvestigationReport(
        investigation_summary="CW-MID-03 follow-on mule pass-through from evidence pack.",
        risk_hypothesis="Shared-device pass-through (pack only).",
        supporting_evidence=[
            EvidenceItem(
                evidence_id="E-TXN",
                type="transaction",
                description="CW-MID-03 $7200 SG->PH",
                source="ledger",
            )
        ],
        recommended_disposition="monitor",
        confidence=55,
        uncertainty="Downstream hop not observed.",
    )
    invented = InvestigationReport(
        investigation_summary="Owned by FAKE-BANK-OWNER-XYZ who launders via Harbour.",
        risk_hypothesis="Invented owner FAKE-BANK-OWNER-XYZ controls the corridor.",
        supporting_evidence=[
            EvidenceItem(
                evidence_id="E-FAKE-OWNER",
                type="entity",
                description="Invented bank owner FAKE-BANK-OWNER-XYZ",
                source="model",
            )
        ],
        recommended_disposition="freeze_account",
        confidence=99,
        uncertainty="",
    )
    gated = apply_grounding_gate(invented, allowed, fallback, [])
    assert gated.grounded is False
    return {
        "risk_level": "HIGH",
        "risk_score": 88,
        "primary_pattern": "mule_pass_through",
        "rationale": (
            "Safety test: model invented an unobserved bank owner; "
            "output gate rejected that claim. Deterministic score unchanged."
        ),
        "recommended_action": gated.recommended_disposition or "monitor",
        "mode": "gemini",
        "provenance": "gate_fail",
        "safety_test": True,
        "gemini_model": "gemini-2.5-flash",
        "dag_risk_score": 88,
        "note": "Safety test — gate rejected ungrounded entities.",
        "investigation_report": gated.model_dump(),
    }


def seed_demo_verdicts() -> int:
    """Cache grounded briefs for hero cases so recordings don't need live Gemini."""
    now = datetime.now(timezone.utc).isoformat()
    briefs = {
        "CW-MID-02": {
            "risk_level": "HIGH",
            "risk_score": 91,
            "primary_pattern": "mule_pass_through",
            "rationale": (
                "Deterministic pack shows rapid SG→PH pass-through on a young account "
                "sharing device D-MID-MULE. Gemini brief cites E-TXN and E-DEV only."
            ),
            "recommended_action": "escalate_fiu",
            "mode": "gemini",
            "provenance": "grounded",
            "gemini_model": "gemini-2.5-flash",
            "dag_risk_score": 91,
            "investigation_report": {
                "investigation_summary": "Middle-bank mule pass-through with shared device.",
                "risk_hypothesis": "Funds rest briefly then exit SG→PH under a new purpose.",
                "supporting_evidence": [
                    {
                        "evidence_id": "E-TXN",
                        "type": "transaction",
                        "description": "CW-MID-02 $9050 SG→PH",
                        "source": "ledger",
                    },
                    {
                        "evidence_id": "E-DEV",
                        "type": "device",
                        "description": "Shared device D-MID-MULE across feeder and exit",
                        "source": "graph",
                    },
                ],
                "contradicting_evidence": [],
                "matched_patterns": ["CW-005"],
                "alternative_explanations": ["Legitimate correspondent cover"],
                "recommended_next_checks": ["Confirm beneficiary KYC at BANK_PH"],
                "recommended_disposition": "escalate_fiu",
                "confidence": 78,
                "uncertainty": "Downstream beyond BANK_PH not observed.",
                "gemini_used": True,
                "grounded": True,
                "model_version": "gemini-2.5-flash",
                "model_provider": "google",
            },
        },
        "CW-LOTUS-04": {
            "risk_level": "HIGH",
            "risk_score": 91,
            "primary_pattern": "mule_pass_through",
            "rationale": "Lotus Ring hero: multi-feeder into SG mule then AE hop.",
            "recommended_action": "hold_payment",
            "mode": "gemini",
            "provenance": "grounded",
            "gemini_model": "gemini-2.5-flash",
            "dag_risk_score": 91,
            "investigation_report": {
                "investigation_summary": "Split feeders into shared SG mule.",
                "risk_hypothesis": "Layered IN→SG→AE corridor.",
                "supporting_evidence": [
                    {
                        "evidence_id": "E-TXN",
                        "type": "transaction",
                        "description": "CW-LOTUS-04 mule exit",
                        "source": "ledger",
                    }
                ],
                "contradicting_evidence": [],
                "matched_patterns": ["CW-001"],
                "alternative_explanations": [],
                "recommended_next_checks": ["Review AE hop KYC"],
                "recommended_disposition": "hold_payment",
                "confidence": 72,
                "uncertainty": "",
                "gemini_used": True,
                "grounded": True,
                "model_version": "gemini-2.5-flash",
                "model_provider": "google",
            },
        },
        "CW-MID-03": _gate_fail_brief_for_mid03(),
    }
    con = connect()
    for txn_id, verdict in briefs.items():
        upsert(
            con,
            "verdicts",
            "txn_id",
            {
                "txn_id": txn_id,
                "verdict": json.dumps(verdict),
                "created_at": now,
                "mode": "gemini",
            },
        )
    con.commit()
    con.close()
    return len(briefs)
