"""
Phase 3 — Adversarial AI Debate System (Prosecutor, Defense, Judge).

Runs a 3-agent debate loop evaluating high-risk alerts to eliminate hallucination
and confirmation bias in financial crime investigations.
"""
from __future__ import annotations

import json
from typing import Any

import audit
import agent as agent_mod
from investigation_dag import run_dag


PROSECUTOR_PROMPT = """You are arguing that this payment should be treated as HIGH RISK and slowed down for human review.
Write for a smart manager who is NOT an AML specialist. Prefer plain English. If you use a term like
"pass-through" or "mule", define it in the same sentence (e.g. "pass-through — money in and out almost immediately").

Your job: build the STRONGEST detailed case that something is wrong, using ONLY the evidence below.
Do not invent accounts, amounts, devices, or counterparties.

CASE EVIDENCE:
{evidence}

Return JSON only (no markdown):
{{
  "case_story": "4-6 sentences narrating what the money appears to have done, in plain English",
  "key_incriminating_evidence": ["6-10 specific facts from the evidence, each one clear sentence"],
  "prosecution_argument": "detailed brief: 3 short paragraphs (or 8-12 sentences). Cover (1) money movement story, (2) why this looks like misuse of accounts rather than ordinary trade, (3) what risk you are asking the judge to take seriously",
  "what_you_want_the_human_to_do": "2-4 plain-English actions (e.g. pause the payment, ask the FIU lead to review)",
  "recommended_severity": "high" | "medium"
}}"""

DEFENSE_PROMPT = """You are arguing that this payment may still be LEGITIMATE business or family remittance.
Write for a smart manager who is NOT an AML specialist. Prefer plain English. Define any technical term in-line.

Your job: build the STRONGEST detailed case for a false alarm or ordinary commercial flow, using ONLY the evidence below.
Do not invent accounts, amounts, devices, or counterparties. Acknowledge weak spots honestly.

CASE EVIDENCE:
{evidence}

Return JSON only (no markdown):
{{
  "case_story": "4-6 sentences narrating an innocent reading of the same facts, in plain English",
  "key_mitigating_evidence": ["6-10 specific facts supporting legitimacy, each one clear sentence"],
  "defense_argument": "detailed brief: 3 short paragraphs (or 8-12 sentences). Cover (1) why the pattern can appear in normal trade, (2) which red flags are weak or incomplete, (3) what a human should verify before treating this as crime",
  "what_you_want_the_human_to_do": "2-4 plain-English checks before escalating (documents, call customer, confirm invoice)",
  "perceived_false_positive_risk": "high" | "medium" | "low"
}}"""

JUDGE_PROMPT = """You are an impartial senior reviewer deciding what a human team should do next.
You are NOT filing a SAR and NOT freezing anything yourself — you recommend.

Write for managers who are not AML specialists. Plain English. Define jargon in-line.
Balance both sides. Be specific. Do not invent facts beyond the evidence.

PROSECUTOR CASE:
{prosecutor}

DEFENSE CASE:
{defense}

CASE EVIDENCE:
{evidence}

Return JSON only (no markdown):
{{
  "final_verdict": "high" | "medium" | "low",
  "confidence_score": <0-100 integer>,
  "plain_english_outcome": "2-3 sentences a senior can read aloud in a meeting: what this case is, and what we recommend",
  "verdict_summary": "detailed synthesis: 5-8 sentences. Cover prosecutor's strongest points, defense's strongest points, what remains unknown, and why you landed where you did",
  "points_for_prosecution": ["3-5 plain bullets of what worried you"],
  "points_for_defense": ["3-5 plain bullets of what still looks ordinary or incomplete"],
  "key_decisive_factor": "one plain sentence naming the single fact that tipped the decision",
  "required_remediation": "plain-English directive for the team (who does what next)",
  "recommended_actions": ["3-5 concrete next steps in everyday language"]
}}"""


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
            config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=4096),
        )
        prosecution = _safe_parse(p_resp.text, {
            "case_story": "Money moved quickly across related accounts in a way that can look like layering.",
            "key_incriminating_evidence": [
                "Funds appear to leave soon after they arrive (short hold).",
                "More than one account may share the same device.",
                "Graph risk score is elevated versus ordinary corridor traffic.",
            ],
            "prosecution_argument": (
                "The payment sits inside a network where money enters and exits quickly. "
                "That pattern is often used to move funds while each single wire looks ordinary. "
                "Until a human confirms a real commercial purpose, treat this as high concern."
            ),
            "what_you_want_the_human_to_do": "Pause the payment and ask an FIU lead to review the network.",
            "recommended_severity": det_verdict.get("risk_level", "high"),
        })

        # 2. Defense Turn
        d_resp = c.models.generate_content(
            model=agent_mod.MODEL,
            contents=DEFENSE_PROMPT.format(evidence=ev_str),
            config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=4096),
        )
        defense = _safe_parse(d_resp.text, {
            "case_story": "The same corridor also carries ordinary supplier and family remittance traffic.",
            "key_mitigating_evidence": [
                "Sender has a registered KYC profile on file.",
                "The corridor itself has real commercial volume.",
                "Not every fast payout is criminal — invoices settle quickly too.",
            ],
            "defense_argument": (
                "Cross-border supplier settlement and family support can look similar to mule flow on a graph. "
                "Shared devices and short holds need context before they become a freeze. "
                "Ask for invoices or a customer call before treating this as confirmed crime."
            ),
            "what_you_want_the_human_to_do": "Request supporting documents and confirm purpose with the customer before escalating.",
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
            config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=4096),
        )
        judge = _safe_parse(j_resp.text, {
            "final_verdict": det_verdict.get("risk_level", "medium"),
            "confidence_score": det_verdict.get("risk_score", 70),
            "plain_english_outcome": "This case needs a human decision; do not clear it on automation alone.",
            "verdict_summary": det_verdict.get("rationale", "Debate completed."),
            "points_for_prosecution": prosecution.get("key_incriminating_evidence", [])[:5],
            "points_for_defense": defense.get("key_mitigating_evidence", [])[:5],
            "key_decisive_factor": "Network risk indicators need human confirmation of purpose.",
            "required_remediation": det_verdict.get("recommended_action", "Manual review by FIU lead"),
            "recommended_actions": [
                "Have an analyst write a one-paragraph case story for the FIU lead.",
                "Confirm whether invoices or remittance purpose documents exist.",
                "Do not freeze or release without an FIU lead decision on high-risk cases.",
            ],
        })

        result = {
            "txn_id": txn_id,
            "prosecutor": prosecution,
            "defense": defense,
            "judge": judge,
            "mode": "gemini_debate",
            "requires_human_review": True,
            "scorecard": debate_scorecard(prosecution, defense, judge),
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
    txn = evidence.get("transaction") or {}
    hold_time = min(
        float(s_risk.get("avg_hold_time_minutes") or 99999),
        float(r_risk.get("avg_hold_time_minutes") or 99999),
    )

    incriminating = []
    if hold_time < 180:
        incriminating.append(
            f"Money tends to leave again within about {hold_time:.0f} minutes — that is unusually fast for ordinary savings."
        )
    if shared_dev:
        incriminating.append(
            f"The same device fingerprint appears across {len(shared_dev)} related accounts — that can mean one phone controlling several people."
        )
    if float(s_risk.get("pass_through_ratio") or 0) > 0.8:
        incriminating.append(
            f"About {float(s_risk.get('pass_through_ratio')):.0%} of incoming money goes straight out again (pass-through)."
        )
    incriminating.append(
        f"Automated risk score is {det_verdict.get('risk_score')} with pattern label '{det_verdict.get('primary_pattern')}'."
    )

    mitigating = [
        f"Sender account {txn.get('sender_id')} is a registered profile in the system.",
        f"Corridor {txn.get('corridor')} also carries ordinary trade and remittance traffic.",
        "A single wire below a threshold can look normal even when the wider network looks odd.",
        "Incomplete network visibility means we may be missing legitimate counterparties.",
    ]

    prosecution = {
        "case_story": (
            f"Payment {txn.get('txn_id')} sits in a network where funds may be moved quickly across accounts on corridor {txn.get('corridor')}. "
            "Each wire can look ordinary alone; the concern is the pattern around it."
        ),
        "key_incriminating_evidence": incriminating,
        "prosecution_argument": (
            f"The automated review flagged pattern '{det_verdict.get('primary_pattern')}' with score {det_verdict.get('risk_score')}. "
            "When money arrives and leaves quickly, or when several accounts share a device, that often means the accounts are being used as temporary holding points rather than as normal customer wallets. "
            "Until a human confirms a real invoice or remittance purpose, treat this as something that should not clear on autopilot."
        ),
        "what_you_want_the_human_to_do": "Pause further payouts on this chain and have an FIU lead review the network view.",
        "recommended_severity": det_verdict.get("risk_level", "high"),
    }
    defense = {
        "case_story": (
            f"The same corridor {txn.get('corridor')} is used for supplier settlement and family support. "
            "Graphs can make ordinary speed look like crime if purpose documents are missing."
        ),
        "key_mitigating_evidence": mitigating,
        "defense_argument": (
            "Legitimate businesses also pay quickly and reuse phones or offices. "
            "A high graph score is a reason to ask questions, not proof of laundering by itself. "
            "Ask for supporting documents and customer context before freezing anyone."
        ),
        "what_you_want_the_human_to_do": "Collect purpose documents and call the customer before escalating.",
        "perceived_false_positive_risk": "low" if det_verdict.get("risk_level") == "low" else "medium",
    }
    judge = {
        "final_verdict": det_verdict.get("risk_level", "medium"),
        "confidence_score": det_verdict.get("risk_score", 65),
        "plain_english_outcome": (
            f"This case is scored {det_verdict.get('risk_level')} ({det_verdict.get('risk_score')}). "
            f"Recommended human step: {det_verdict.get('recommended_action', 'manual review')}."
        ),
        "verdict_summary": (
            f"Both sides have a point. The prosecutor is right that the network pattern around {txn.get('txn_id')} looks unusual for a single ordinary payment. "
            "The defense is right that the same signals can appear in real trade if invoices and purpose are not yet in the file. "
            f"Automated rationale: {det_verdict.get('rationale')}. "
            "A human should decide whether to hold, escalate, or clear — the model does not freeze accounts."
        ),
        "points_for_prosecution": incriminating[:5],
        "points_for_defense": mitigating[:5],
        "key_decisive_factor": (
            f"Pattern '{det_verdict.get('primary_pattern')}' with score {det_verdict.get('risk_score')} still needs purpose confirmation."
        ),
        "required_remediation": det_verdict.get("recommended_action", "Proceed with analyst disposition."),
        "recommended_actions": [
            "Open the investigation network view and write a one-paragraph case story for a senior.",
            "Ask for invoices or remittance purpose documents.",
            "If risk stays high, route hold/freeze/escalate to an FIU lead only.",
        ],
    }
    return {
        "txn_id": txn_id,
        "prosecutor": prosecution,
        "defense": defense,
        "judge": judge,
        "mode": "deterministic_debate",
        "note": note,
        "requires_human_review": True,
        "scorecard": debate_scorecard(prosecution, defense, judge),
    }


def debate_scorecard(prosecution: dict, defense: dict, judge: dict) -> dict:
    return {
        "prosecution_evidence": len(prosecution.get("key_incriminating_evidence") or []),
        "defense_evidence": len(defense.get("key_mitigating_evidence") or []),
        "judge_confidence": judge.get("confidence_score"),
        "key_disagreement": judge.get("key_decisive_factor") or "",
    }


def _safe_parse(text: str, fallback: dict) -> dict:
    if not text:
        return fallback
    clean = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(clean)
        if not isinstance(parsed, dict):
            return fallback
        out = dict(fallback)
        out.update(parsed)
        return out
    except json.JSONDecodeError:
        return fallback


if __name__ == "__main__":
    # ponytail: one assert that plain-language fields exist on the offline path
    sample = _deterministic_debate(
        "T-demo",
        {
            "transaction": {"txn_id": "T-demo", "sender_id": "A1", "corridor": "US-IN"},
            "sender_risk": {"avg_hold_time_minutes": 20, "pass_through_ratio": 0.95},
            "receiver_risk": {},
            "shared_devices": [{"device_id": "d1"}],
        },
        {"risk_level": "high", "risk_score": 88, "primary_pattern": "mule_pass_through",
         "rationale": "demo", "recommended_action": "Hold for FIU lead review"},
    )
    assert len(sample["prosecutor"]["key_incriminating_evidence"]) >= 3
    assert len(sample["judge"]["verdict_summary"].split()) > 40
    assert "plain_english_outcome" in sample["judge"]
    print("agent_debate self-check ok")
