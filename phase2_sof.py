"""
Phase 2 — Source-of-funds plausibility check.

Reasons over free-text SoF explanation vs profile + transaction evidence.
Returns specific inconsistencies (not a single opaque score). Analyst-facing draft only.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from db import connect
import audit
import agent as agent_mod


INCOME_KEYWORDS = {
    "salary": ["salary", "payroll", "wages", "employment"],
    "business": ["business", "invoice", "client", "trade", "sale"],
    "savings": ["savings", "saved", "deposit"],
    "inheritance": ["inheritance", "estate", "will"],
    "loan": ["loan", "credit", "borrow"],
    "gift": ["gift", "family gift", "donation"],
}


def _extract_claimed_sources(text: str) -> list[str]:
    text_l = (text or "").lower()
    found = []
    for label, kws in INCOME_KEYWORDS.items():
        if any(k in text_l for k in kws):
            found.append(label)
    return found or ["unspecified"]


def _amount_vs_income(amount: float, income: float) -> str | None:
    if income <= 0:
        return "Stated income is zero/unknown while a material transfer is claimed."
    if amount > income * 0.5:
        return f"Transfer amount ${amount:,.0f} exceeds 50% of stated annual income ${income:,.0f}."
    if amount > income * 0.25:
        return f"Transfer amount ${amount:,.0f} is high relative to stated annual income ${income:,.0f}."
    return None


def deterministic_sof_check(txn_id: str, explanation: str | None = None) -> dict[str, Any]:
    con = connect()
    txn = con.execute(
        "SELECT * FROM flagged_transactions WHERE txn_id=?", (txn_id,)
    ).fetchone() or con.execute("SELECT * FROM transactions WHERE txn_id=?", (txn_id,)).fetchone()
    if not txn:
        con.close()
        raise ValueError("transaction not found")
    txn = dict(txn)
    sender = con.execute("SELECT * FROM accounts WHERE account_id=?", (txn["sender_id"],)).fetchone()
    receiver = con.execute("SELECT * FROM accounts WHERE account_id=?", (txn["receiver_id"],)).fetchone()
    sender_risk = con.execute("SELECT * FROM risk_scores WHERE account_id=?", (txn["sender_id"],)).fetchone()
    receiver_risk = con.execute("SELECT * FROM risk_scores WHERE account_id=?", (txn["receiver_id"],)).fetchone()
    recent = con.execute(
        "SELECT amount, purpose, source_of_funds, ts FROM transactions "
        "WHERE sender_id=? OR receiver_id=? ORDER BY ts DESC LIMIT 8",
        (txn["sender_id"], txn["receiver_id"]),
    ).fetchall()
    con.close()

    explanation = explanation or txn.get("source_of_funds") or ""
    purpose = txn.get("purpose") or ""
    claimed = _extract_claimed_sources(explanation)
    inconsistencies: list[dict] = []

    for side_name, profile, risk in (
        ("sender", dict(sender) if sender else None, dict(sender_risk) if sender_risk else {}),
        ("receiver", dict(receiver) if receiver else None, dict(receiver_risk) if receiver_risk else {}),
    ):
        if not profile:
            continue
        occ = (profile.get("occupation") or "").lower()
        income = float(profile.get("stated_income_usd") or 0)
        age = risk.get("account_age_days")
        amt = float(txn["amount"])

        flag = _amount_vs_income(amt, income)
        if flag and side_name in {"sender", "receiver"}:
            # Prefer party that owns the funds narrative (sender for outbound remittance)
            if side_name == "sender" or txn["receiver_id"] == profile["account_id"]:
                inconsistencies.append({
                    "code": "amount_vs_income",
                    "party": side_name,
                    "detail": flag,
                })

        if "salary" in claimed and occ in {"unemployed", "student", "intern"}:
            inconsistencies.append({
                "code": "occupation_mismatch",
                "party": side_name,
                "detail": f"Claimed salary-sourced funds but occupation is '{profile.get('occupation')}'.",
            })

        if "inheritance" in claimed and amt < 1000:
            inconsistencies.append({
                "code": "narrative_scale",
                "party": side_name,
                "detail": "Inheritance narrative is atypical for sub-$1,000 transfers.",
            })

        if age is not None and age <= 7 and "savings" in claimed:
            inconsistencies.append({
                "code": "account_age_vs_savings",
                "party": side_name,
                "detail": f"Account opened {age}d ago — long-term savings narrative is weakly supported.",
            })

        if risk.get("pass_through_ratio", 0) >= 0.85 and "business" in claimed:
            inconsistencies.append({
                "code": "pass_through_vs_business",
                "party": side_name,
                "detail": "Near-total pass-through is inconsistent with retaining business operating funds.",
            })

    # purpose vs sof lexical clash
    if purpose and explanation:
        if "family" in purpose.lower() and "business" in explanation.lower():
            inconsistencies.append({
                "code": "purpose_sof_clash",
                "party": "transaction",
                "detail": f"Purpose '{purpose}' conflicts with business-oriented SoF explanation.",
            })

    # burst of similar SoF strings
    sof_values = [r["source_of_funds"] for r in recent if r["source_of_funds"]]
    if sof_values and explanation:
        same = sum(1 for s in sof_values if s.lower() == explanation.lower())
        if same >= 4:
            inconsistencies.append({
                "code": "repeated_verbatim_sof",
                "party": "transaction",
                "detail": f"Identical SoF text reused across {same} recent related transfers.",
            })

    severity = "high" if len(inconsistencies) >= 3 else ("medium" if inconsistencies else "low")
    draft = {
        "txn_id": txn_id,
        "explanation_analyzed": explanation,
        "claimed_sources": claimed,
        "inconsistencies": inconsistencies,
        "plausibility": "implausible" if severity == "high" else ("questionable" if severity == "medium" else "plausible"),
        "severity": severity,
        "analyst_prompt": (
            "Review the listed inconsistencies against customer documents before any hold/release decision."
        ),
        "mode": "deterministic",
        "requires_human_review": True,
    }
    audit.log(txn_id, "sof_check", draft, actor="phase2")
    return draft


def sof_check(txn_id: str, explanation: str | None = None, use_llm: bool = True) -> dict[str, Any]:
    base = deterministic_sof_check(txn_id, explanation)
    if not use_llm or not agent_mod.gemini_available():
        return base
    try:
        from google.genai import types
        c = agent_mod.client()
        prompt = (
            "You are a compliance analyst drafting a source-of-funds plausibility review. "
            "Given the structured findings JSON, refine the inconsistency list and write a "
            "short analyst-facing draft paragraph. Return JSON with keys: "
            "inconsistencies (array of {code,party,detail}), draft_narrative (string), "
            "plausibility (plausible|questionable|implausible). Do not decide to file a SAR."
            f"\n\nFINDINGS:\n{json.dumps(base, default=str)}"
        )
        resp = c.models.generate_content(
            model=agent_mod.active_model(),
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2),
        )
        text = (resp.text or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        refined = json.loads(text)
        base["inconsistencies"] = refined.get("inconsistencies", base["inconsistencies"])
        base["draft_narrative"] = refined.get("draft_narrative")
        base["plausibility"] = refined.get("plausibility", base["plausibility"])
        base["mode"] = "gemini"
        allowed = agent_mod.evidence_allowed_text(base)
        if isinstance(base.get("draft_narrative"), str):
            grounded, n = agent_mod.ground_plain_text(base["draft_narrative"], allowed)
            base["draft_narrative"] = grounded or base["draft_narrative"]
            base["grounding_rewrites"] = n
            base["grounded"] = True
        audit.log(txn_id, "sof_check_llm", {"plausibility": base["plausibility"]}, actor="phase2")
    except Exception as e:
        base["llm_note"] = f"LLM refine skipped: {e}"
    return base
