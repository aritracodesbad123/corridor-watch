"""
Phase 3 — Adversarial AI Debate System (Prosecutor, Defense, Judge).

Runs a 3-agent debate loop evaluating high-risk alerts to eliminate hallucination
and confirmation bias in financial crime investigations.
"""
from __future__ import annotations

import json
from typing import Any

from db import connect
import audit
import agent as agent_mod
from investigation_dag import run_dag, deterministic_verdict


PROSECUTOR_PROMPT = """You are a Financial Crime Prosecutor Agent.
Your goal is to construct the STRONGEST argument that this transaction is FRAUDULENT or LAUNDERING.
Focus strictly on suspicious indicators: short hold times, high pass-through ratio, shared devices/beneficiaries,
corridor velocity spikes, and high-risk named patterns.

CASE EVIDENCE:
{evidence}

Return JSON with keys:
{
  "key_incriminating_evidence": ["list of 3-5 specific facts from data"],
  "prosecution_argument": "2-3 sentence persuasive case for fraud",
  "recommended_severity": "high" | "medium"
}"""

DEFENSE_PROMPT = """You are a Financial Crime Defense Agent.
Your goal is to construct the STRONGEST legitimate business / human explanation for this transaction.
Focus on mitigating factors: account KYC tier, stated income, valid remittance corridors, reasonable business purpose,
or potential false-positive triggers.

CASE EVIDENCE:
{evidence}

Return JSON with keys:
{
  "key_mitigating_evidence": ["list of 3-5 specific facts supporting legitimacy"],
  "defense_argument": "2-3 sentence persuasive explanation of legitimacy",
  "perceived_false_positive_risk": "high" | "medium" | "low"
}"""

JUDGE_PROMPT = """You are an impartial FIU Chief Compliance Judge.
You have heard the Prosecutor's case and the Defense's counter-arguments.

PROSECUTOR CASE:
{prosecutor}

DEFENSE CASE:
{defense}

CASE EVIDENCE:
{evidence}

Synthesize both sides and issue a final, unbiased verdict.
Return JSON:
{
  "final_verdict": "high" | "medium" | "low",
  "confidence_score": <0-100 integer>,
  "verdict_summary": "3-4 sentence comprehensive synthesis balancing both sides",
  "key_decisive_factor": "the single most compelling fact that tipped the decision",
  "required_remediation": "concrete directive for the compliance team"
}"""


def run_debate(txn_id: str, use_llm: bool = True) -> dict[str, Any]:
    audit.log(txn_id, "debate_start", {"txn_id": txn_id}, actor="agent_debate")
    dag_bundle = run_dag(txn_id)
    evidence = dag_bundle["evidence"]
    det_verdict = dag_bundle["verdict"]

    if not use_llm or not agent_mod.gemini_available():
        return _deterministic_debate(txn_id, evidence, det_verdict)

    try:
        from google.genai import types
        c = agent_mod.client()

        ev_str = json.dumps(evidence, default=str)

        # 1. Prosecutor Turn
        p_resp = c.models.generate_content(
            model=agent_mod.MODEL,
            contents=PROSECUTOR_PROMPT.format(evidence=ev_str),
            config=types.GenerateContentConfig(temperature=0.3),
        )
        prosecution = _safe_parse(p_resp.text, {
            "key_incriminating_evidence": ["High pass-through ratio", "Short fund hold time"],
            "prosecution_argument": "Evidence shows characteristics of remittance pass-through mule activity.",
            "recommended_severity": det_verdict.get("risk_level", "high"),
        })

        # 2. Defense Turn
        d_resp = c.models.generate_content(
            model=agent_mod.MODEL,
            contents=DEFENSE_PROMPT.format(evidence=ev_str),
            config=types.GenerateContentConfig(temperature=0.3),
        )
        defense = _safe_parse(d_resp.text, {
            "key_mitigating_evidence": ["Stated income on profile", "Valid corridor pairing"],
            "defense_argument": "Transfer may represent legitimate family support or SME trade remittance.",
            "perceived_false_positive_risk": "medium",
        })

        # 3. Judge Synthesis Turn
        j_resp = c.models.generate_content(
            model=agent_mod.MODEL,
            contents=JUDGE_PROMPT.format(
                prosecutor=json.dumps(prosecution),
                defense=json.dumps(defense),
                evidence=ev_str,
            ),
            config=types.GenerateContentConfig(temperature=0.2),
        )
        judge = _safe_parse(j_resp.text, {
            "final_verdict": det_verdict.get("risk_level", "medium"),
            "confidence_score": det_verdict.get("risk_score", 70),
            "verdict_summary": det_verdict.get("rationale", "Debate completed."),
            "key_decisive_factor": "Graph risk indicators and hold time metrics.",
            "required_remediation": det_verdict.get("recommended_action", "Manual review"),
        })

        result = {
            "txn_id": txn_id,
            "prosecutor": prosecution,
            "defense": defense,
            "judge": judge,
            "mode": "gemini_debate",
            "requires_human_review": True,
        }
        audit.log(txn_id, "debate_complete", {"judge_verdict": judge.get("final_verdict")}, actor="agent_debate")
        return result

    except Exception as e:
        audit.log(txn_id, "debate_error", {"error": str(e)}, actor="agent_debate")
        return _deterministic_debate(txn_id, evidence, det_verdict, note=f"LLM debate fallback: {e}")


def _deterministic_debate(txn_id: str, evidence: dict, det_verdict: dict, note: str = "") -> dict:
    s_risk = evidence.get("sender_risk") or {}
    r_risk = evidence.get("receiver_risk") or {}
    shared_dev = evidence.get("shared_devices") or []
    hold_time = min(
        float(s_risk.get("avg_hold_time_minutes") or 99999),
        float(r_risk.get("avg_hold_time_minutes") or 99999),
    )

    incriminating = []
    if hold_time < 180:
        incriminating.append(f"Rapid fund velocity with short hold time ({hold_time:.0f} mins)")
    if shared_dev:
        incriminating.append(f"Device fingerprint shared across {len(shared_dev)} peer accounts")
    if s_risk.get("pass_through_ratio", 0) > 0.8:
        incriminating.append(f"Near total pass-through ratio ({s_risk.get('pass_through_ratio')})")

    mitigating = [
        f"Registered KYC account for sender {evidence.get('transaction', {}).get('sender_id')}",
        f"Corridor {evidence.get('transaction', {}).get('corridor')} has established trade flows",
    ]

    prosecution = {
        "key_incriminating_evidence": incriminating or ["Elevated composite risk score"],
        "prosecution_argument": f"Transaction demonstrates primary fraud pattern '{det_verdict.get('primary_pattern')}' with elevated network velocity.",
        "recommended_severity": det_verdict.get("risk_level", "high"),
    }
    defense = {
        "key_mitigating_evidence": mitigating,
        "defense_argument": "Transfer falls within typical cross-border remittance parameters for this corridor.",
        "perceived_false_positive_risk": "low" if det_verdict.get("risk_level") == "low" else "medium",
    }
    judge = {
        "final_verdict": det_verdict.get("risk_level", "medium"),
        "confidence_score": det_verdict.get("risk_score", 65),
        "verdict_summary": f"Grounded in 12-step DAG evidence. {det_verdict.get('rationale')}",
        "key_decisive_factor": f"Pattern '{det_verdict.get('primary_pattern')}' score of {det_verdict.get('risk_score')}.",
        "required_remediation": det_verdict.get("recommended_action", "Proceed with analyst disposition."),
    }
    return {
        "txn_id": txn_id,
        "prosecutor": prosecution,
        "defense": defense,
        "judge": judge,
        "mode": "deterministic_debate",
        "note": note,
        "requires_human_review": True,
    }


def _safe_parse(text: str, fallback: dict) -> dict:
    if not text:
        return fallback
    clean = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return fallback
