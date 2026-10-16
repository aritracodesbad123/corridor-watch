"""
Phase 3 — Multi-Jurisdiction SAR Regulatory Narrative Generator.

Generates official regulatory filing narratives compliant with:
- FinCEN (US BSA / Form 111 SAR)
- MAS (Singapore Monetary Authority / STR)
- AUSTRAC (Australia SMR)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from db import connect
import audit
import agent as agent_mod
from investigation_dag import run_dag


FINCEN_PROMPT = """You are an Anti-Money Laundering (AML) Compliance Specialist drafting an official FinCEN SAR (Suspicious Activity Report) narrative under US BSA regulations.

CASE DETAILS:
{evidence}

Draft a formal FinCEN SAR Narrative in 4 structured sections:
1. SUMMARY OF SUSPICIOUS ACTIVITY (overview of primary pattern, amounts, dates)
2. SUBJECT & ACCOUNT CHARACTERISTICS (KYC, occupation, account age, income)
3. METHODOLOGY & MONEY MOVEMENT (graph flow, pass-through, hold time, shared devices)
4. ACTION TAKEN BY FINANCIAL INSTITUTION (hold, escalation, watchlist)

Return ONLY JSON:
{{
  "jurisdiction": "FinCEN (United States)",
  "filing_form": "FinCEN Form 111 SAR",
  "narrative_sections": {{
    "section_1_summary": string,
    "section_2_subject_profile": string,
    "section_3_methodology": string,
    "section_4_institution_action": string
  }},
  "full_narrative_text": string,
  "suspected_structuring_flag": boolean
}}"""

MAS_PROMPT = """You are a Compliance Officer in Singapore drafting a Suspicious Transaction Report (STR) for the Commercial Affairs Department (CAD) / MAS.

CASE DETAILS:
{evidence}

Draft a formal MAS STR Narrative in 3 structured sections:
PART A: SUBJECT & REMITTANCE CORRIDOR DETAILS
PART B: DETECTED FRAUD TYPOLOGY & MONEY FLOW (fan-in, pass-through, velocity)
PART C: GROUNDS FOR SUSPICION & RECOMMENDED COMPLIANCE ACTION

Return ONLY JSON:
{{
  "jurisdiction": "MAS (Singapore)",
  "filing_form": "MAS CAD STR Form A",
  "narrative_sections": {{
    "part_a_subject": string,
    "part_b_typology": string,
    "part_c_grounds": string
  }},
  "full_narrative_text": string,
  "mas_corridor_flag": boolean
}}"""

AUSTRAC_PROMPT = """You are an AML Compliance Officer in Australia drafting a Suspicious Matter Report (SMR) for AUSTRAC.

CASE DETAILS:
{evidence}

Draft a formal AUSTRAC SMR Narrative in 3 structured sections:
PART 1: SUSPICIOUS MATTER SUMMARY (corridor, value, velocity)
PART 2: CUSTOMER & COUNTERPARTY IDENTITY (KYC, device fingerprinting, biometrics)
PART 3: REASONABLE GROUNDS FOR SUSPICION (mule indicator, short hold time, pass-through)

Return ONLY JSON:
{{
  "jurisdiction": "AUSTRAC (Australia)",
  "filing_form": "AUSTRAC SMR Form B",
  "narrative_sections": {{
    "part_1_summary": string,
    "part_2_identity": string,
    "part_3_grounds": string
  }},
  "full_narrative_text": string,
  "austrac_threshold_flag": boolean
}}"""


def generate_sar(
    txn_id: str,
    jurisdiction: str = "fincen",
    use_llm: bool = True,
) -> dict[str, Any]:
    jurisdiction = (jurisdiction or "fincen").lower()
    audit.log(txn_id, "sar_generate_start", {"jurisdiction": jurisdiction}, actor="sar_generator")

    dag_bundle = run_dag(txn_id)
    evidence = dag_bundle["evidence"]
    verdict = dag_bundle["verdict"]

    if not use_llm or not agent_mod.gemini_available():
        return _templated_sar(txn_id, jurisdiction, evidence, verdict)

    try:
        from google.genai import types
        c = agent_mod.client()
        ev_str = json.dumps(evidence, default=str)

        if jurisdiction == "mas":
            prompt = MAS_PROMPT.format(evidence=ev_str)
        elif jurisdiction == "austrac":
            prompt = AUSTRAC_PROMPT.format(evidence=ev_str)
        else:
            prompt = FINCEN_PROMPT.format(evidence=ev_str)

        resp = c.models.generate_content(
            model=agent_mod.active_model(),
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                thinking_config=agent_mod._thinking_off(),
            ),
        )
        data = _safe_parse(resp.text)
        data["txn_id"] = txn_id
        data["generated_at"] = datetime.now(timezone.utc).isoformat()
        data["mode"] = "gemini"
        data["requires_human_review"] = True
        data = _ground_sar(data, evidence, verdict)
        audit.log(txn_id, "sar_generate_complete", {"jurisdiction": jurisdiction}, actor="sar_generator")
        return data

    except Exception as e:
        audit.log(txn_id, "sar_generate_error", {"error": str(e)}, actor="sar_generator")
        return _templated_sar(txn_id, jurisdiction, evidence, verdict, note=f"LLM draft fallback: {e}")


def _ground_sar(data: dict, evidence: dict, verdict: dict) -> dict:
    allowed = agent_mod.evidence_allowed_text(evidence, json.dumps(verdict, default=str))
    rewrites = 0
    sections = data.get("narrative_sections") or {}
    if isinstance(sections, dict):
        for k, v in list(sections.items()):
            if isinstance(v, str):
                grounded, n = agent_mod.ground_plain_text(v, allowed)
                rewrites += n
                sections[k] = grounded or v
        data["narrative_sections"] = sections
    if isinstance(data.get("full_narrative_text"), str):
        grounded, n = agent_mod.ground_plain_text(data["full_narrative_text"], allowed)
        rewrites += n
        if grounded:
            data["full_narrative_text"] = grounded
    data["grounded"] = True
    data["grounding_rewrites"] = rewrites
    return data


def _templated_sar(txn_id: str, jurisdiction: str, evidence: dict, verdict: dict, note: str = "") -> dict:
    txn = evidence.get("transaction") or {}
    amount = float(txn.get("amount") or 0)
    corridor = txn.get("corridor") or "IN->SG"
    pattern = verdict.get("primary_pattern") or "mule_pass_through"
    sender_id = txn.get("sender_id")
    receiver_id = txn.get("receiver_id")

    risk_level = str(verdict.get("risk_level") or "medium").upper()
    risk_score = verdict.get("risk_score")
    occupation = (evidence.get("sender_profile") or {}).get("occupation") or "not stated"
    action = verdict.get("recommended_action") or "manual review"

    if jurisdiction == "mas":
        sec1 = (
            f"Subject remittance {txn_id} for {amount:,.2f} USD on corridor {corridor}. "
            f"Ordering customer {sender_id}; beneficiary {receiver_id}."
        )
        sec2 = (
            f"Detected typology: {pattern} (risk score {risk_score}). "
            "Network indicators include rapid onward movement and/or shared-device linkages inconsistent with a single ordinary remittance."
        )
        sec3 = (
            f"Grounds for suspicion: activity is inconsistent with the customer profile on file. "
            f"Institution action: {action}. This draft requires human review before STR filing."
        )
        full_text = (
            "MAS CAD STR — Form A narrative draft\n\n"
            f"PART A — Subject & remittance corridor\n{sec1}\n\n"
            f"PART B — Detected typology & money flow\n{sec2}\n\n"
            f"PART C — Grounds for suspicion & compliance action\n{sec3}"
        )
        return {
            "txn_id": txn_id,
            "jurisdiction": "MAS (Singapore)",
            "filing_form": "MAS CAD STR Form A",
            "narrative_sections": {
                "part_a_subject": sec1,
                "part_b_typology": sec2,
                "part_c_grounds": sec3,
            },
            "section_titles": {
                "part_a_subject": "PART A — Subject & remittance corridor",
                "part_b_typology": "PART B — Detected typology & money flow",
                "part_c_grounds": "PART C — Grounds for suspicion & compliance action",
            },
            "full_narrative_text": full_text,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "deterministic_template",
            "note": note,
            "requires_human_review": True,
        }

    if jurisdiction == "austrac":
        sec1 = (
            f"Suspicious matter {txn_id}: value {amount:,.2f} USD on corridor {corridor}."
        )
        sec2 = (
            f"Customer {sender_id} paid beneficiary {receiver_id}. "
            "Shared-device or shared-beneficiary signals in the investigation graph support a possible mule network."
        )
        sec3 = (
            f"Reasonable grounds: automated review rated {risk_level} risk (score {risk_score}) "
            f"with pattern {pattern}. Recommended step: {action}. Human review required before SMR submission."
        )
        full_text = (
            "AUSTRAC SMR — Form B narrative draft\n\n"
            f"PART 1 — Suspicious matter summary\n{sec1}\n\n"
            f"PART 2 — Customer & counterparty identity\n{sec2}\n\n"
            f"PART 3 — Reasonable grounds for suspicion\n{sec3}"
        )
        return {
            "txn_id": txn_id,
            "jurisdiction": "AUSTRAC (Australia)",
            "filing_form": "AUSTRAC SMR Form B",
            "narrative_sections": {
                "part_1_summary": sec1,
                "part_2_identity": sec2,
                "part_3_grounds": sec3,
            },
            "section_titles": {
                "part_1_summary": "PART 1 — Suspicious matter summary",
                "part_2_identity": "PART 2 — Customer & counterparty identity",
                "part_3_grounds": "PART 3 — Reasonable grounds for suspicion",
            },
            "full_narrative_text": full_text,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "deterministic_template",
            "note": note,
            "requires_human_review": True,
        }

    # FinCEN Form 111 — narrative parts (not a PDF form fill)
    sec1 = (
        f"Suspicious activity summary for transfer {txn_id}: {amount:,.2f} USD on corridor {corridor}. "
        f"Primary pattern {pattern}; overall risk {risk_level} (score {risk_score})."
    )
    sec2 = (
        f"Subject account {sender_id} initiated payment to {receiver_id}. "
        f"Stated occupation on file: {occupation}."
    )
    sec3 = (
        f"Activity / methodology: investigation graph shows {pattern}-consistent movement "
        "(e.g. short hold times, pass-through, or shared devices). Individual wires may look ordinary in isolation."
    )
    sec4 = (
        f"Institution action: {action}. Case logged for compliance review. "
        "This narrative is a draft for human authorization before FinCEN Form 111 filing."
    )
    full_text = (
        "FinCEN Form 111 SAR — narrative draft\n\n"
        f"Part I — Summary of suspicious activity\n{sec1}\n\n"
        f"Part II — Subject & account characteristics\n{sec2}\n\n"
        f"Part III — Methodology & money movement\n{sec3}\n\n"
        f"Part IV — Action taken by the financial institution\n{sec4}"
    )
    return {
        "txn_id": txn_id,
        "jurisdiction": "FinCEN (United States)",
        "filing_form": "FinCEN Form 111 SAR",
        "narrative_sections": {
            "section_1_summary": sec1,
            "section_2_subject_profile": sec2,
            "section_3_methodology": sec3,
            "section_4_institution_action": sec4,
        },
        "section_titles": {
            "section_1_summary": "Part I — Summary of suspicious activity",
            "section_2_subject_profile": "Part II — Subject & account characteristics",
            "section_3_methodology": "Part III — Methodology & money movement",
            "section_4_institution_action": "Part IV — Action taken by the financial institution",
        },
        "full_narrative_text": full_text,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "deterministic_template",
        "note": note,
        "requires_human_review": True,
    }


def _safe_parse(text: str) -> dict:
    if not text:
        return {}
    clean = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return {}
