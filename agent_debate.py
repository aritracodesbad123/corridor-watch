"""
Phase 3 — Adversarial AI Debate System (Prosecutor, Defense, Judge).

Runs a 3-agent debate loop evaluating high-risk alerts to eliminate hallucination
and confirmation bias in financial crime investigations.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import audit
import agent as agent_mod
from investigation_dag import run_dag

# Keep briefs readable but bounded so Vertex finishes faster than the 8–12 sentence / 4k-token path.
_SIDE_TOKENS = 1536
_JUDGE_TOKENS = 2048

PROSECUTOR_PROMPT = """You are arguing that this payment should be treated as HIGH RISK and slowed down for human review.
Write for a smart manager who is NOT an AML specialist. Prefer plain English. Define jargon in-line
(e.g. "pass-through — money in and out almost immediately").

Use ONLY the evidence below. Do not invent accounts, amounts, devices, or counterparties.
Be concise but concrete — denser than a few bullets, not a long essay.

CASE EVIDENCE:
{evidence}

Return JSON only (no markdown):
{{
  "case_story": "3-4 plain-English sentences on what the money appears to have done",
  "key_incriminating_evidence": ["4-6 specific facts, each one clear sentence"],
  "prosecution_argument": "5-7 sentences covering money movement, why it looks like misuse vs ordinary trade, and the risk a human should take seriously",
  "what_you_want_the_human_to_do": "1-2 plain-English actions",
  "recommended_severity": "high" | "medium"
}}"""

DEFENSE_PROMPT = """You are arguing that this payment may still be LEGITIMATE business or family remittance.
Write for a smart manager who is NOT an AML specialist. Prefer plain English. Define jargon in-line.

Use ONLY the evidence below. Do not invent accounts, amounts, devices, or counterparties.
Acknowledge weak spots. Be concise but concrete.

CASE EVIDENCE:
{evidence}

Return JSON only (no markdown):
{{
  "case_story": "3-4 plain-English sentences with an innocent reading of the same facts",
  "key_mitigating_evidence": ["4-6 specific facts supporting legitimacy, each one clear sentence"],
  "defense_argument": "5-7 sentences covering why this can be normal trade, which red flags are weak, and what to verify before treating it as crime",
  "what_you_want_the_human_to_do": "1-2 plain-English checks before escalating",
  "perceived_false_positive_risk": "high" | "medium" | "low"
}}"""

JUDGE_PROMPT = """You are an impartial senior reviewer deciding what a human team should do next.
You recommend only — you do not file a SAR or freeze accounts.

Plain English for non-AML managers. Define jargon in-line. Balance both sides. Do not invent facts.

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
  "plain_english_outcome": "2 sentences a senior can read aloud: what this case is, and what we recommend",
  "verdict_summary": "4-6 sentences covering strongest points on each side, what is unknown, and why you landed here",
  "points_for_prosecution": ["3-4 plain bullets"],
  "points_for_defense": ["3-4 plain bullets"],
  "key_decisive_factor": "one plain sentence naming the fact that tipped the decision",
  "required_remediation": "plain-English directive (who does what next)",
  "recommended_actions": ["3-4 concrete next steps in everyday language"]
}}"""

# Keys that matter for debate; drop bulky session/neighborhood dumps.
_EVIDENCE_KEYS = (
    "transaction",
    "sender_risk",
    "receiver_risk",
    "shared_devices",
    "shared_beneficiaries",
    "corridor_velocity",
    "named_patterns",
    "deterministic_verdict",
    "document_verification",
)


def _compact_evidence(evidence: dict) -> dict:
    """Shrink the prompt so prompt tokens (and latency) stay bounded."""
    out: dict[str, Any] = {}
    for key in _EVIDENCE_KEYS:
        if key not in evidence:
            continue
        val = evidence[key]
        if isinstance(val, list):
            out[key] = val[:8]
        else:
            out[key] = val
    return out


def _gen_json(prompt: str, *, max_output_tokens: int, temperature: float) -> str:
    """One Gemini call via the shared path (thinking off + JSON mime)."""
    c = agent_mod.client()
    # ponytail: reuse agent._generate_content; add temp kw when that helper grows a temp arg
    from google.genai import types
    thinking = agent_mod._thinking_off()
    kwargs: dict[str, Any] = {
        "max_output_tokens": max_output_tokens,
        "temperature": temperature,
        "response_mime_type": "application/json",
    }
    if thinking is not None:
        kwargs["thinking_config"] = thinking
    resp = c.models.generate_content(
        model=agent_mod.active_model(),
        contents=prompt,
        config=types.GenerateContentConfig(**kwargs),
    )
    agent_mod._record_usage(resp)
    return getattr(resp, "text", None) or ""


def run_debate(txn_id: str, use_llm: bool = True) -> dict[str, Any]:
    audit.log(txn_id, "debate_start", {"txn_id": txn_id}, actor="agent_debate")
    dag_bundle = run_dag(txn_id)
    evidence = dag_bundle["evidence"]
    det_verdict = dag_bundle["verdict"]

    if not use_llm or not agent_mod.gemini_available():
        return _deterministic_debate(txn_id, evidence, det_verdict)

    try:
        ev_str = json.dumps(_compact_evidence(evidence), default=str)

        p_fallback = {
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
        }
        d_fallback = {
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
        }

        # Prosecutor and Defense are independent — run them together.
        with ThreadPoolExecutor(max_workers=2) as pool:
            p_fut = pool.submit(
                _gen_json,
                PROSECUTOR_PROMPT.format(evidence=ev_str),
                max_output_tokens=_SIDE_TOKENS,
                temperature=0.3,
            )
            d_fut = pool.submit(
                _gen_json,
                DEFENSE_PROMPT.format(evidence=ev_str),
                max_output_tokens=_SIDE_TOKENS,
                temperature=0.3,
            )
            prosecution = _safe_parse(p_fut.result(), p_fallback)
            defense = _safe_parse(d_fut.result(), d_fallback)

        judge = _safe_parse(
            _gen_json(
                JUDGE_PROMPT.format(
                    prosecutor=json.dumps(prosecution),
                    defense=json.dumps(defense),
                    evidence=ev_str,
                ),
                max_output_tokens=_JUDGE_TOKENS,
                temperature=0.2,
            ),
            {
                "final_verdict": det_verdict.get("risk_level", "medium"),
                "confidence_score": det_verdict.get("risk_score", 70),
                "plain_english_outcome": "This case needs a human decision; do not clear it on automation alone.",
                "verdict_summary": det_verdict.get("rationale", "Debate completed."),
                "points_for_prosecution": prosecution.get("key_incriminating_evidence", [])[:4],
                "points_for_defense": defense.get("key_mitigating_evidence", [])[:4],
                "key_decisive_factor": "Network risk indicators need human confirmation of purpose.",
                "required_remediation": det_verdict.get("recommended_action", "Manual review by FIU lead"),
                "recommended_actions": [
                    "Have an analyst write a one-paragraph case story for the FIU lead.",
                    "Confirm whether invoices or remittance purpose documents exist.",
                    "Do not freeze or release without an FIU lead decision on high-risk cases.",
                ],
            },
        )

        result = {
            "txn_id": txn_id,
            "prosecutor": prosecution,
            "defense": defense,
            "judge": judge,
            "mode": "gemini_debate",
            "requires_human_review": True,
            "scorecard": debate_scorecard(prosecution, defense, judge),
        }
        result = _ground_debate_result(result, evidence, det_verdict)
        audit.log(txn_id, "debate_complete", {"judge_verdict": judge.get("final_verdict")}, actor="agent_debate")
        return result

    except Exception as e:
        audit.log(txn_id, "debate_error", {"error": str(e)}, actor="agent_debate")
        return _deterministic_debate(txn_id, evidence, det_verdict, note=f"LLM debate fallback: {e}")


def _ground_debate_result(result: dict, evidence: dict, det_verdict: dict) -> dict:
    allowed = agent_mod.evidence_allowed_text(evidence, json.dumps(det_verdict, default=str))
    rewrites = 0
    grounded = True

    def _g(s: str) -> str:
        nonlocal rewrites, grounded
        out, n = agent_mod.ground_plain_text(s or "", allowed)
        rewrites += n
        if n and not out:
            grounded = False
        return out or (s if n == 0 else out)

    def _gl(items: list) -> list:
        nonlocal rewrites
        out, n = agent_mod.ground_string_list(list(items or []), allowed)
        rewrites += n
        return out

    p = result.get("prosecutor") or {}
    d = result.get("defense") or {}
    j = result.get("judge") or {}
    for side, keys in (
        (p, ("case_story", "prosecution_argument", "what_you_want_the_human_to_do")),
        (d, ("case_story", "defense_argument", "what_you_want_the_human_to_do")),
        (j, (
            "plain_english_outcome", "verdict_summary", "key_decisive_factor",
            "required_remediation",
        )),
    ):
        for k in keys:
            if k in side and isinstance(side.get(k), str):
                side[k] = _g(side[k])
    if "key_incriminating_evidence" in p:
        p["key_incriminating_evidence"] = _gl(p.get("key_incriminating_evidence"))
    if "key_mitigating_evidence" in d:
        d["key_mitigating_evidence"] = _gl(d.get("key_mitigating_evidence"))
    for k in ("points_for_prosecution", "points_for_defense", "recommended_actions"):
        if k in j:
            j[k] = _gl(j.get(k))
    result["prosecutor"] = p
    result["defense"] = d
    result["judge"] = j
    result["grounded"] = bool(grounded)
    result["grounding_rewrites"] = rewrites
    _persist_debate(result.get("txn_id") or "", result)
    return result


def _persist_debate(txn_id: str, result: dict) -> None:
    from db import connect, upsert
    con = connect()
    try:
        upsert(con, "debates", "txn_id", {
            "txn_id": txn_id,
            "payload": json.dumps(result, default=str),
            "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        })
        con.commit()
    except Exception:
        pass
    finally:
        con.close()


def get_cached_debate(txn_id: str) -> dict | None:
    from db import connect
    con = connect()
    try:
        row = con.execute("SELECT payload FROM debates WHERE txn_id=?", (txn_id,)).fetchone()
    finally:
        con.close()
    if not row:
        return None
    try:
        return json.loads(row["payload"] if hasattr(row, "keys") else row[0])
    except Exception:
        return None


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
    return _ground_debate_result({
        "txn_id": txn_id,
        "prosecutor": prosecution,
        "defense": defense,
        "judge": judge,
        "mode": "deterministic_debate",
        "note": note,
        "requires_human_review": True,
        "scorecard": debate_scorecard(prosecution, defense, judge),
    }, evidence, det_verdict)


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
    assert "plain_english_outcome" in sample["judge"]
    compact = _compact_evidence({
        "transaction": {"txn_id": "T"},
        "sender_sessions": [{"x": 1}] * 50,
        "shared_devices": list(range(20)),
    })
    assert "sender_sessions" not in compact
    assert len(compact["shared_devices"]) == 8
    print("agent_debate self-check ok")
