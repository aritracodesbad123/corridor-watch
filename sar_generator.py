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
            model=agent_mod.MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2),
        )
        data = _safe_parse(resp.text)
        data["txn_id"] = txn_id
        data["generated_at"] = datetime.now(timezone.utc).isoformat()
        data["mode"] = "gemini"
        data["requires_human_review"] = True

        audit.log(txn_id, "sar_generate_complete", {"jurisdiction": jurisdiction}, actor="sar_generator")
        return data

    except Exception as e:
        audit.log(txn_id, "sar_generate_error", {"error": str(e)}, actor="sar_generator")
        return _templated_sar(txn_id, jurisdiction, evidence, verdict, note=f"LLM draft fallback: {e}")


def _templated_sar(txn_id: str, jurisdiction: str, evidence: dict, verdict: dict, note: str = "") -> dict:
    txn = evidence.get("transaction") or {}
    amount = float(txn.get("amount") or 0)
    corridor = txn.get("corridor") or "IN->SG"
    pattern = verdict.get("primary_pattern") or "mule_pass_through"
    sender_id = txn.get("sender_id")
    receiver_id = txn.get("receiver_id")

    if jurisdiction == "mas":
        sec1 = f"Transaction {txn_id} involving ${amount:,.2f} USD on corridor {corridor} from sender {sender_id} to receiver {receiver_id}."
        sec2 = f"Primary detected typology is '{pattern}' with risk score {verdict.get('risk_score')}. Pass-through fund movement observed within 24 hours."
        sec3 = f"Grounds for suspicion: Fund transfer behavior inconsistent with customer declared profile. Action taken: Payment held pending enhanced due diligence."
        full_text = f"MAS STR NARRATIVE:\n\nPART A:\n{sec1}\n\nPART B:\n{sec2}\n\nPART C:\n{sec3}"
        return {
            "txn_id": txn_id,
            "jurisdiction": "MAS (Singapore)",
            "filing_form": "MAS CAD STR Form A",
            "narrative_sections": {"part_a_subject": sec1, "part_b_typology": sec2, "part_c_grounds": sec3},
            "full_narrative_text": full_text,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "deterministic_template",
            "note": note,
            "requires_human_review": True,
        }

    elif jurisdiction == "austrac":
        sec1 = f"Suspicious matter reported for transfer {txn_id} amounting to ${amount:,.2f} on corridor {corridor}."
        sec2 = f"Customer {sender_id} transferred funds to beneficiary {receiver_id}. Device biometrics and shared beneficiary patterns indicate potential mule network activity."
        sec3 = f"Reasonable grounds for suspicion based on rule-based DAG verdict rating of {verdict.get('risk_level').upper()} risk."
        full_text = f"AUSTRAC SMR NARRATIVE:\n\nPART 1:\n{sec1}\n\nPART 2:\n{sec2}\n\nPART 3:\n{sec3}"
        return {
            "txn_id": txn_id,
            "jurisdiction": "AUSTRAC (Australia)",
            "filing_form": "AUSTRAC SMR Form B",
            "narrative_sections": {"part_1_summary": sec1, "part_2_identity": sec2, "part_3_grounds": sec3},
            "full_narrative_text": full_text,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "deterministic_template",
            "note": note,
            "requires_human_review": True,
        }

    else:  # fincen
        sec1 = f"FinCEN SAR filing regarding suspicious remittance transfer {txn_id} totaling ${amount:,.2f} on corridor {corridor}."
        sec2 = f"Subject account {sender_id} initiated transfer to receiver {receiver_id}. Stated occupation: {evidence.get('sender_profile', {}).get('occupation', 'N/A')}."
        sec3 = f"Methodology involves pattern '{pattern}' with score {verdict.get('risk_score')}. Short hold times and pass-through fund movement indicate layering."
        sec4 = f"Financial institution has placed transaction on investigative hold and logged event for compliance review."
        full_text = f"FINCEN SAR NARRATIVE:\n\nSECTION 1:\n{sec1}\n\nSECTION 2:\n{sec2}\n\nSECTION 3:\n{sec3}\n\nSECTION 4:\n{sec4}"
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
