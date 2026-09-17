"""
Phase 3 — Multimodal Source-of-Funds (SoF) Document Verification.

Analyzes customer-submitted documents (invoices, paystubs, bank statements)
using Gemini Vision / Multimodal processing and cross-checks figures against
database transaction evidence.
"""
from __future__ import annotations

import json
from typing import Any

from db import connect
import audit
import agent as agent_mod


MULTIMODAL_PROMPT = """You are a compliance document verification AI.
Inspect the attached document image / content and extract the following:
1. document_type (e.g. "Invoice", "Bank Statement", "Tax Form", "Paystub")
2. issuer_name (name of issuing company or bank)
3. document_date (YYYY-MM-DD format if visible)
4. total_amount (numerical value in USD equivalent)
5. authenticity_indicators (e.g. "Official bank letterhead visible", "Stamp present")
6. potential_red_flags (e.g. "Font mismatch", "Altered transaction line", "None")

Return ONLY JSON:
{
  "document_type": string,
  "issuer_name": string,
  "document_date": string,
  "total_amount": number,
  "authenticity_indicators": [string],
  "potential_red_flags": [string],
  "summary": string
}"""


ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/jpg", "image/webp", "application/pdf",
}
MAX_BYTES = 8 * 1024 * 1024


def latest_verification(txn_id: str) -> dict[str, Any] | None:
    from db import init_schema
    init_schema()
    con = connect()
    row = con.execute(
        "SELECT result, filename, mime_type, created_at FROM document_verifications WHERE txn_id=?",
        (txn_id,),
    ).fetchone()
    con.close()
    if not row:
        return None
    try:
        data = json.loads(row["result"])
    except (json.JSONDecodeError, TypeError):
        return None
    data["filename"] = row["filename"]
    data["stored_at"] = row["created_at"]
    return data


def _persist(txn_id: str, filename: str | None, mime_type: str, result: dict) -> None:
    from datetime import datetime, timezone
    from db import init_schema, upsert
    init_schema()
    con = connect(row_factory=False)
    upsert(con, "document_verifications", "txn_id", {
        "txn_id": txn_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "filename": filename or "",
        "mime_type": mime_type,
        "result": json.dumps(result, default=str),
    })
    con.commit()
    con.close()


def _extract_with_gemini(image_bytes: bytes, mime_type: str) -> dict:
    from google.genai import types
    c = agent_mod.client()
    try:
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    except Exception:
        part = types.Part(inline_data=types.Blob(data=image_bytes, mime_type=mime_type))
    resp = c.models.generate_content(
        model=agent_mod.active_model(),
        contents=[MULTIMODAL_PROMPT, part],
        config=types.GenerateContentConfig(temperature=0.1),
    )
    parsed = _safe_parse(getattr(resp, "text", None) or "")
    if not parsed:
        raise ValueError("Gemini returned an unreadable document extraction")
    return _coerce_extracted(parsed)


def verify_document(
    txn_id: str,
    image_bytes: bytes | None = None,
    mime_type: str = "image/png",
    sample_doc_name: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    audit.log(txn_id, "doc_verify_start", {"txn_id": txn_id, "sample": sample_doc_name, "filename": filename}, actor="multimodal_sof")
    con = connect()
    txn = con.execute("SELECT * FROM flagged_transactions WHERE txn_id=?", (txn_id,)).fetchone()
    if not txn:
        txn = con.execute("SELECT * FROM transactions WHERE txn_id=?", (txn_id,)).fetchone()
    con.close()
    if not txn:
        raise ValueError(f"transaction {txn_id} not found")
    txn = dict(txn)
    txn_amount = float(txn.get("amount") or 0)

    extracted = None
    vision_error = None
    if image_bytes:
        if len(image_bytes) > MAX_BYTES:
            raise ValueError("document exceeds 8 MB limit")
        mime_type = (mime_type or "application/octet-stream").split(";")[0].strip().lower()
        if mime_type == "image/jpg":
            mime_type = "image/jpeg"
        if mime_type not in ALLOWED_MIME:
            raise ValueError(f"unsupported document type: {mime_type}. Upload a PNG, JPEG, WebP, or PDF.")
        if agent_mod.gemini_available():
            try:
                extracted = _extract_with_gemini(image_bytes, mime_type)
            except Exception as e:
                vision_error = str(e)
                audit.log(txn_id, "doc_verify_vision_error", {"error": vision_error}, actor="multimodal_sof")
        else:
            vision_error = "GEMINI_API_KEY not available for vision extraction"

    if not extracted and image_bytes:
        extracted = {
            "document_type": "Uploaded document",
            "issuer_name": "unreadable",
            "document_date": "",
            "total_amount": 0,
            "authenticity_indicators": [],
            "potential_red_flags": [f"Vision extraction failed: {vision_error or 'unknown error'}"],
            "summary": "The uploaded file was stored, but figures could not be read automatically. Analyst review required.",
        }
    elif not extracted:
        extracted = _simulated_document_extraction(txn, sample_doc_name)
    extracted = _coerce_extracted(extracted)

    doc_amount = _to_amount(extracted.get("total_amount"))
    diff = abs(doc_amount - txn_amount)
    pct_diff = (diff / txn_amount * 100) if txn_amount > 0 else 0

    if pct_diff <= 5.0:
        match_status = "VERIFIED_MATCH"
        match_note = f"Extracted document amount ${doc_amount:,.2f} matches claimed transaction amount ${txn_amount:,.2f} (within 5%)."
    elif doc_amount > 0:
        match_status = "AMOUNT_DISCREPANCY"
        match_note = f"Extracted document amount ${doc_amount:,.2f} differs from wire amount ${txn_amount:,.2f} by {pct_diff:.1f}%."
    else:
        match_status = "UNVERIFIED_FORMAT"
        match_note = "Could not verify total amount from document image."

    result = {
        "txn_id": txn_id,
        "transaction_amount": txn_amount,
        "extracted_document": extracted,
        "verification_status": match_status,
        "verification_note": match_note,
        "discrepancy_percentage": round(pct_diff, 1),
        "requires_human_review": match_status != "VERIFIED_MATCH",
        "filename": filename,
        "mime_type": mime_type,
        "vision_error": vision_error,
        "used_upload": bool(image_bytes),
    }
    allowed = agent_mod.evidence_allowed_text(txn, json.dumps(extracted, default=str), match_note)
    note, n = agent_mod.ground_plain_text(match_note, allowed)
    if note:
        result["verification_note"] = note
    if isinstance(extracted.get("summary"), str):
        summary, n2 = agent_mod.ground_plain_text(extracted["summary"], allowed)
        n += n2
        if summary:
            extracted["summary"] = summary
            result["extracted_document"] = extracted
    result["grounded"] = True
    result["grounding_rewrites"] = n
    _persist(txn_id, filename, mime_type, result)
    audit.log(txn_id, "doc_verify_complete", {"status": match_status, "filename": filename}, actor="multimodal_sof")
    return result


def _simulated_document_extraction(txn: dict, sample_name: str | None = None) -> dict:
    amt = float(txn.get("amount") or 0)
    purpose = (txn.get("purpose") or "").lower()

    if "payroll" in purpose or "salary" in purpose:
        return {
            "document_type": "Official Monthly Paystub",
            "issuer_name": "Apex Global Solutions Pte Ltd",
            "document_date": "2026-08-28",
            "total_amount": amt,
            "authenticity_indicators": ["Corporate letterhead verified", "HR digital seal present"],
            "potential_red_flags": [],
            "summary": f"Paystub matches exact transfer amount of ${amt:,.2f}.",
        }
    elif "trade" in purpose or "business" in purpose or "invoice" in purpose:
        return {
            "document_type": "Commercial Export Invoice",
            "issuer_name": "Pacific Trade Logistics Corp",
            "document_date": "2026-08-25",
            "total_amount": round(amt * 1.02, 2),
            "authenticity_indicators": ["Tax registration ID matches", "Shipping bill attached"],
            "potential_red_flags": ["Minor shipping fee variance (+2%)"],
            "summary": f"Commercial trade invoice matches wire transfer within 2% variance.",
        }
    else:
        # Default mismatch scenario for high risk alerts
        return {
            "document_type": "Personal Remittance Slip",
            "issuer_name": "Local Express Exchange",
            "document_date": "2026-08-30",
            "total_amount": round(amt * 0.35, 2),
            "authenticity_indicators": ["Receipt number present"],
            "potential_red_flags": ["Document amount is 65% lower than wire transfer amount", "Handwritten alteration on date"],
            "summary": f"Document amount (${amt * 0.35:,.2f}) is significantly lower than wire transfer (${amt:,.2f}).",
        }


def _to_amount(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("$", "").replace("USD", "").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0


def _coerce_extracted(extracted: dict) -> dict:
    data = dict(extracted or {})
    data["total_amount"] = _to_amount(data.get("total_amount"))
    if not isinstance(data.get("authenticity_indicators"), list):
        data["authenticity_indicators"] = []
    if not isinstance(data.get("potential_red_flags"), list):
        data["potential_red_flags"] = []
    return data


def _safe_parse(text: str) -> dict:
    if not text:
        return {}
    clean = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(clean)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        start, end = clean.find("{"), clean.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(clean[start : end + 1])
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}
