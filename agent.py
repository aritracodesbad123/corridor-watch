"""
Agentic investigation layer.

Modes:
  - deterministic: 12-step DAG only (no LLM)
  - gemini: DAG evidence + Gemini reasoning over investigation tools
  - auto: try Gemini; fall back to deterministic on missing key / errors

Provider-agnostic prompt + tool schemas; only the client SDK swaps for Azure.

Gemini client compatibility:
  - google-genai >= 2.3.0 exposes client.interactions (preferred for Gemini 3.x tools)
  - google-genai 1.x only has client.models.generate_content
The code detects the installed SDK and uses whichever surface exists.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from db import DatabaseBusy, connect, upsert
import audit
from investigation_dag import run_dag, deterministic_verdict
from investigations.schemas import EvidenceItem, InvestigationReport

class VerdictSchema(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    risk_score: int = Field(ge=0, le=100)
    primary_pattern: Literal[
        "mule_pass_through", "split_transaction_laundering", "shared_device_ring",
        "synthetic_identity", "multi_hop_chain", "elevated_activity"
    ]
    rationale: str = Field(min_length=1, max_length=1200)
    recommended_action: str = Field(min_length=1, max_length=300)
    evidence_refs: list[str] = Field(default_factory=list, max_length=12)


ALLOWED_EVIDENCE_REFS = {
    "sender_risk", "receiver_risk", "shared_devices", "shared_beneficiaries",
    "sender_sessions", "receiver_sessions", "corridor_velocity", "named_patterns",
    "network_neighborhood", "transaction", "evidence_pack", "document_verification",
}


MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
_client = None

# Set for the duration of a single investigate_with_gemini() call so the tool
# functions below can attach the right case id to their audit log entries.
_CURRENT_TXN_ID: str | None = None


def _use_vertex() -> bool:
    forced = (os.getenv("GEMINI_BACKEND") or "").lower()
    if forced in {"vertex", "vertexai"}:
        return True
    if forced in {"developer", "ai_studio", "apistudio"}:
        return False
    return os.getenv("ENVIRONMENT", "") == "gcp" and bool(os.getenv("GOOGLE_CLOUD_PROJECT"))


def gemini_available() -> bool:
    if _use_vertex():
        return True
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def gemini_backend() -> str:
    return "vertex" if _use_vertex() else "developer"


def client():
    global _client
    if _client is None:
        from google import genai
        if _use_vertex():
            project = os.getenv("GOOGLE_CLOUD_PROJECT") or ""
            if not project:
                raise RuntimeError("GOOGLE_CLOUD_PROJECT is required for Vertex Gemini")
            location = os.getenv("VERTEX_LOCATION") or os.getenv("GEMINI_LOCATION") or "global"
            _client = genai.Client(vertexai=True, project=project, location=location)
        else:
            key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not key:
                raise RuntimeError("GEMINI_API_KEY is not set")
            _client = genai.Client(api_key=key)
    return _client


# ---------- investigation tools (shared by DAG consumers + LLM) ----------

def get_account_context(account_id: str) -> dict:
    """Fetch an account's profile, computed risk features, recent transaction
    activity, and recent login/payment sessions."""
    audit.log(_CURRENT_TXN_ID, "tool_call", {"tool": "get_account_context", "args": {"account_id": account_id}}, actor="gemini")
    con = connect()
    acc = con.execute("SELECT * FROM accounts WHERE account_id=?", (account_id,)).fetchone()
    risk = con.execute("SELECT * FROM risk_scores WHERE account_id=?", (account_id,)).fetchone()
    counterparties = con.execute(
        "SELECT sender_id, receiver_id, amount, ts, corridor FROM transactions "
        "WHERE sender_id=? OR receiver_id=? ORDER BY ts DESC LIMIT 10",
        (account_id, account_id),
    ).fetchall()
    sessions = con.execute(
        "SELECT * FROM sessions WHERE account_id=? ORDER BY started_at DESC LIMIT 3",
        (account_id,),
    ).fetchall()
    con.close()
    risk_d = dict(risk) if risk else {}
    if risk_d.get("pattern_scores"):
        try:
            risk_d["pattern_scores"] = json.loads(risk_d["pattern_scores"])
        except json.JSONDecodeError:
            pass
    result = {
        "profile": dict(acc) if acc else {"note": "external/unregistered counterparty"},
        "risk_features": risk_d,
        "recent_activity": [dict(r) for r in counterparties],
        "sessions": [dict(r) for r in sessions],
    }
    audit.log(_CURRENT_TXN_ID, "tool_result", {"tool": "get_account_context", "keys": list(result)}, actor="gemini")
    return result


def get_shared_devices(account_id: str) -> dict:
    """List other accounts that share a device fingerprint with this account."""
    audit.log(_CURRENT_TXN_ID, "tool_call", {"tool": "get_shared_devices", "args": {"account_id": account_id}}, actor="gemini")
    con = connect()
    rows = con.execute(
        """SELECT ad.device_id, d.fingerprint, d.os, ad2.account_id AS peer_account
           FROM account_devices ad
           JOIN devices d ON d.device_id = ad.device_id
           JOIN account_devices ad2 ON ad2.device_id = ad.device_id
           WHERE ad.account_id=? AND ad2.account_id != ? LIMIT 25""",
        (account_id, account_id),
    ).fetchall()
    con.close()
    result = {"account_id": account_id, "shared_with": [dict(r) for r in rows]}
    audit.log(_CURRENT_TXN_ID, "tool_result", {"tool": "get_shared_devices", "keys": list(result)}, actor="gemini")
    return result


def get_session_biometrics(account_id: str) -> dict:
    """Fetch recent behavioral biometric session features for an account."""
    audit.log(_CURRENT_TXN_ID, "tool_call", {"tool": "get_session_biometrics", "args": {"account_id": account_id}}, actor="gemini")
    con = connect()
    rows = con.execute(
        "SELECT * FROM sessions WHERE account_id=? ORDER BY started_at DESC LIMIT 5",
        (account_id,),
    ).fetchall()
    con.close()
    result = {"account_id": account_id, "sessions": [dict(r) for r in rows]}
    audit.log(_CURRENT_TXN_ID, "tool_result", {"tool": "get_session_biometrics", "keys": list(result)}, actor="gemini")
    return result


def get_network_neighborhood(txn_id: str) -> dict:
    """Fetch the transaction-graph neighborhood around a transaction id."""
    audit.log(_CURRENT_TXN_ID, "tool_call", {"tool": "get_network_neighborhood", "args": {"txn_id": txn_id}}, actor="gemini")
    from graph_features import network_subgraph
    result = network_subgraph(txn_id)
    audit.log(_CURRENT_TXN_ID, "tool_result", {"tool": "get_network_neighborhood"}, actor="gemini")
    return result


TOOLS = {
    "get_account_context": get_account_context,
    "get_shared_devices": get_shared_devices,
    "get_session_biometrics": get_session_biometrics,
    "get_network_neighborhood": get_network_neighborhood,
}


_INTERACTIONS_BLOCKED = False


def _interactions_blocked_error(exc: BaseException) -> bool:
    text = str(exc)
    return any(
        token in text
        for token in (
            "API_KEY_SERVICE_BLOCKED",
            "CreateInteractionHttp are blocked",
            "InteractionsService.CreateInteractionHttp",
        )
    )


def _has_interactions(c) -> bool:
    """Interactions is opt-in. Many API keys allow generate_content but block v1beta Interactions."""
    if _INTERACTIONS_BLOCKED:
        return False
    if os.getenv("GEMINI_USE_INTERACTIONS", "").lower() not in {"1", "true", "yes"}:
        return False
    return hasattr(c, "interactions") and hasattr(getattr(c, "interactions", None), "create")


def _tool_declarations() -> list[dict]:
    """Plain JSON-schema function declarations, as required by the
    Interactions API (a list of dicts, not SDK type objects)."""
    return [
        {
            "type": "function",
            "name": "get_account_context",
            "description": "Fetch account profile, risk features, recent activity, sessions.",
            "parameters": {"type": "object", "properties": {"account_id": {"type": "string"}}, "required": ["account_id"]},
        },
        {
            "type": "function",
            "name": "get_shared_devices",
            "description": "List other accounts sharing devices with this account.",
            "parameters": {"type": "object", "properties": {"account_id": {"type": "string"}}, "required": ["account_id"]},
        },
        {
            "type": "function",
            "name": "get_session_biometrics",
            "description": "Fetch behavioral biometric session features for an account.",
            "parameters": {"type": "object", "properties": {"account_id": {"type": "string"}}, "required": ["account_id"]},
        },
        {
            "type": "function",
            "name": "get_network_neighborhood",
            "description": "Fetch graph neighborhood around a transaction id.",
            "parameters": {"type": "object", "properties": {"txn_id": {"type": "string"}}, "required": ["txn_id"]},
        },
    ]


GROUNDED_SYSTEM_PROMPT = """You are an evidence-grounded financial-crime investigation copilot
for Corridor Watch. You are NOT an autonomous decision engine.

Hard rules:
1. Use only supplied evidence. Never invent transaction IDs, accounts, customers, countries, or amounts.
2. Reference evidence_id values from the supplied evidence list when making claims.
3. Distinguish observed evidence from inference.
4. State uncertainty explicitly if evidence is insufficient.
5. Provide at least one plausible legitimate/alternative explanation.
6. Never claim that a hold, freeze, or FIU filing has already occurred.
7. Never invent regulatory requirements.
8. Never make a final high-risk decision — only recommend a disposition for a human.
9. Return valid JSON matching the required schema. No markdown fences.
"""


SYSTEM_PROMPT = """You are a financial-crime investigator assistant for cross-border
payments compliance (JAPAC remittance corridors). You investigate flagged transactions.

Available tools:
- get_account_context(account_id)
- get_shared_devices(account_id)
- get_session_biometrics(account_id)
- get_network_neighborhood(txn_id)

After gathering evidence, return ONLY a JSON object (no markdown fences):
{
  "risk_level": "low" | "medium" | "high",
  "risk_score": <0-100 integer>,
  "primary_pattern": "<mule_pass_through | split_transaction_laundering | shared_device_ring | synthetic_identity | multi_hop_chain | elevated_activity>",
  "rationale": "<2-4 sentences grounded in retrieved evidence>",
  "recommended_action": "<one concrete next step>",
  "evidence_refs": ["<tool or feature names you relied on>"]
}
Ground every claim in tool data. Do not invent counterparties, amounts, or devices.
If document_verification is present, treat it as analyst-supplied source-of-funds
evidence and reconcile extracted amounts against the wire. Do not invent document figures.
Only use evidence_refs from: transaction, sender_risk, receiver_risk, sender_sessions,
receiver_sessions, shared_devices, shared_beneficiaries, corridor_velocity,
named_patterns, network_neighborhood, evidence_pack, document_verification."""


def _call_with_retry(c, **kwargs):
    global _INTERACTIONS_BLOCKED
    from google.genai import errors as genai_errors
    delays = [1, 2]
    for attempt, delay in enumerate([0] + delays):
        if delay:
            time.sleep(delay)
        try:
            if not _has_interactions(c):
                raise AttributeError("Client object has no attribute 'interactions'")
            return c.interactions.create(**kwargs)
        except Exception as e:
            if _interactions_blocked_error(e):
                _INTERACTIONS_BLOCKED = True
                raise
            if isinstance(e, getattr(genai_errors, "ServerError", ())) and "UNAVAILABLE" in str(e) and attempt < len(delays):
                continue
            raise


def _generate_content(c, *, model: str, contents: Any, tools: list[dict] | None = None):
    """Fallback for google-genai 1.x / any Client without Interactions."""
    from google.genai import types
    config_kwargs: dict[str, Any] = {}
    if tools:
        declarations = []
        for tool in tools:
            declarations.append(types.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description") or "",
                parameters=tool.get("parameters") or {"type": "object", "properties": {}},
            ))
        config_kwargs["tools"] = [types.Tool(function_declarations=declarations)]
    return c.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(**config_kwargs) if config_kwargs else None,
    )


def _function_calls_from_response(response) -> list[tuple[str, dict]]:
    calls: list[tuple[str, dict]] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            fc = getattr(part, "function_call", None)
            if not fc or not getattr(fc, "name", None):
                continue
            args = dict(fc.args) if getattr(fc, "args", None) else {}
            calls.append((fc.name, args))
    return calls


def _complete_text(c, prompt: str) -> str:
    """Single-shot completion used by the grounded report path."""
    if _has_interactions(c):
        interaction = _call_with_retry(
            c,
            model=MODEL,
            store=False,
            input=[{"type": "user_input", "content": [{"type": "text", "text": prompt}]}],
        )
        return interaction.output_text or ""
    response = _generate_content(c, model=MODEL, contents=prompt)
    return getattr(response, "text", None) or ""


def _parse_verdict(text: str, fallback_score: float) -> dict:
    text = (text or "").strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        raw = json.loads(text)
        # Validate and normalize model output before it can reach the case cache.
        parsed = VerdictSchema.model_validate(raw)
        data = parsed.model_dump()
        data["evidence_refs"] = [r for r in data["evidence_refs"] if r in ALLOWED_EVIDENCE_REFS]
        data["mode"] = "gemini"
        return data
    except (json.JSONDecodeError, ValueError):
        return {
            "risk_level": "medium",
            "risk_score": max(0, min(100, int(fallback_score))),
            "primary_pattern": "elevated_activity",
            "rationale": "Gemini returned an invalid or insufficiently structured verdict; deterministic evidence remains authoritative.",
            "recommended_action": "manual review",
            "evidence_refs": ["evidence_pack"],
            "mode": "gemini_parse_error",
        }


def investigate_with_gemini(txn: dict, dag_bundle: dict | None = None) -> dict:
    global _CURRENT_TXN_ID
    c = client()
    payload = {"transaction": txn}
    if dag_bundle:
        payload["dag_deterministic_verdict"] = dag_bundle.get("verdict")
        payload["dag_evidence_keys"] = list((dag_bundle.get("evidence") or {}).keys())
        payload["dag_evidence"] = _safe_evidence(dag_bundle.get("evidence") or {})
    try:
        from multimodal_sof import latest_verification
        doc = latest_verification(txn.get("txn_id") or "")
        if doc:
            payload["document_verification"] = doc
    except Exception:
        pass

    txn_id = txn.get("txn_id", "")
    _CURRENT_TXN_ID = txn_id
    tools = _tool_declarations()
    prompt = SYSTEM_PROMPT + "\n\n" + json.dumps(payload, default=str)

    try:
        global _INTERACTIONS_BLOCKED
        if not _has_interactions(c):
            return _investigate_with_generate_content(c, txn, prompt, tools)

        # Stateless Interactions mode (store=False): append each returned step
        # verbatim so Gemini 3.x thought signatures stay intact.
        try:
            history = [{
                "type": "user_input",
                "content": [{"type": "text", "text": prompt}],
            }]
            for _ in range(8):
                interaction = _call_with_retry(c, model=MODEL, store=False, input=history, tools=tools)

                for step in interaction.steps:
                    history.append(step.model_dump())

                fc_steps = [s for s in interaction.steps if s.type == "function_call"]
                if fc_steps:
                    for fc in fc_steps:
                        fn = TOOLS.get(fc.name)
                        args = fc.arguments or {}
                        result = fn(**args) if fn else {"error": f"unknown tool {fc.name}"}
                        history.append({
                            "type": "function_result",
                            "name": fc.name,
                            "call_id": fc.id,
                            "result": [{"type": "text", "text": json.dumps(result, default=str)}],
                        })
                    continue

                text = interaction.output_text or ""
                verdict = _parse_verdict(text, txn.get("risk_score", 0))
                audit.log(txn_id, "gemini_verdict", verdict, actor="gemini")
                return verdict
        except Exception as exc:
            if _interactions_blocked_error(exc):
                global _INTERACTIONS_BLOCKED
                _INTERACTIONS_BLOCKED = True
                return _investigate_with_generate_content(c, txn, prompt, tools)
            raise
    finally:
        _CURRENT_TXN_ID = None

    return {
        "risk_level": "unknown",
        "risk_score": int(txn.get("risk_score", 0)),
        "primary_pattern": "tool_loop_exceeded",
        "rationale": "Investigation exceeded tool-call budget.",
        "recommended_action": "manual review",
        "mode": "gemini",
    }


def _prefetch_tool_results(txn: dict) -> dict:
    """Run investigation tools locally so Gemini 3 never needs a function-call turn."""
    sender = txn.get("sender_id")
    receiver = txn.get("receiver_id")
    txn_id = txn.get("txn_id")
    pack: dict[str, Any] = {}
    if sender:
        pack["get_account_context_sender"] = TOOLS["get_account_context"](sender)
        pack["get_shared_devices_sender"] = TOOLS["get_shared_devices"](sender)
        pack["get_session_biometrics_sender"] = TOOLS["get_session_biometrics"](sender)
    if receiver:
        pack["get_account_context_receiver"] = TOOLS["get_account_context"](receiver)
        pack["get_shared_devices_receiver"] = TOOLS["get_shared_devices"](receiver)
    if txn_id:
        pack["get_network_neighborhood"] = TOOLS["get_network_neighborhood"](txn_id)
    return pack


def _investigate_with_generate_content(c, txn: dict, prompt: str, tools: list[dict]) -> dict:
    """Single-shot generate_content path.

    Gemini 3.x requires thought_signature on every functionCall part. Older
    google-genai builds drop that field when we echo history, which yields
    INVALID_ARGUMENT. Prefetch tools locally and do not declare tools to the
    model on this path. The Interactions API still uses live function calling.
    """
    del tools  # reserved for the Interactions path only
    tool_pack = _prefetch_tool_results(txn)
    full_prompt = (
        prompt
        + "\n\nPre-fetched tool results. Use only this evidence; do not invent IDs or amounts.\n"
        + json.dumps(tool_pack, default=str)
    )
    response = _generate_content(c, model=MODEL, contents=full_prompt, tools=None)
    text = getattr(response, "text", None) or ""
    verdict = _parse_verdict(text, txn.get("risk_score", 0))
    audit.log(txn.get("txn_id", ""), "gemini_verdict", verdict, actor="gemini")
    return verdict


def grounded_gemini_report(
    txn: dict,
    evidence: list[EvidenceItem],
    matches: list[dict],
    risk: dict | None,
    network: dict,
    fallback: InvestigationReport,
) -> InvestigationReport:
    """Ask Gemini to reason over a closed evidence set. Falls back if output is ungrounded."""
    import time as _time
    started = _time.perf_counter()
    from metrics import METRICS
    from config import get_settings

    METRICS.inc("gemini_requests_total")
    allowed_ids = {e.evidence_id for e in evidence}
    try:
        from multimodal_sof import latest_verification
        doc_payload = latest_verification(txn.get("txn_id") or "")
    except Exception:
        doc_payload = None
    payload = {
        "transaction": {k: txn.get(k) for k in (
            "txn_id", "sender_id", "receiver_id", "amount", "currency", "corridor", "ts",
            "purpose", "source_of_funds", "primary_pattern", "fraud_scenario", "risk_score",
        )},
        "network_features": (network or {}).get("features"),
        "account_risk": {k: (risk or {}).get(k) for k in (
            "risk_score", "primary_pattern", "account_age_days", "pass_through_ratio",
            "avg_hold_time_minutes", "shared_device_count", "fan_in_count",
        )},
        "evidence": [e.model_dump() for e in evidence],
        "pattern_matches": matches,
        "document_verification": doc_payload,
        "required_output": {
            "investigation_summary": "string",
            "risk_hypothesis": "string",
            "supporting_evidence": [{"evidence_id": "E-...", "type": "", "description": "", "source": "", "source_ref": "", "confidence": 1.0}],
            "contradicting_evidence": [],
            "matched_patterns": ["CW-001"],
            "alternative_explanations": ["..."],
            "recommended_next_checks": ["..."],
            "recommended_disposition": "clear|monitor|hold_payment|escalate_fiu|freeze_account",
            "confidence": 0,
            "uncertainty": "string",
        },
    }
    c = client()
    text = _complete_text(c, GROUNDED_SYSTEM_PROMPT + "\n\n" + json.dumps(payload, default=str)).strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    METRICS.gemini_latency.add((_time.perf_counter() - started) * 1000.0)
    raw = json.loads(text)
    report = InvestigationReport.model_validate(raw)
    # Drop invented evidence IDs so hallucination is visible and harmless.
    def _filter(items: list[EvidenceItem]) -> list[EvidenceItem]:
        kept = []
        for item in items:
            if item.evidence_id in allowed_ids or item.evidence_id.startswith("E-"):
                if item.evidence_id in allowed_ids:
                    kept.append(item)
        return kept or evidence[:3]
    report.supporting_evidence = _filter(report.supporting_evidence)
    report.contradicting_evidence = [e for e in report.contradicting_evidence if e.evidence_id in allowed_ids]
    report.matched_patterns = [p for p in report.matched_patterns if any(m["pattern_id"] == p for m in matches)] or [m["pattern_id"] for m in matches[:3]]
    report.gemini_used = True
    report.grounded = True
    report.model_version = get_settings().gemini_model
    report.pattern_versions = [f"{m['pattern_id']}@v{m.get('version', 1)}" for m in matches]
    return report


def _attach_platform_report(txn_id: str, dag_bundle: dict, verdict: dict) -> InvestigationReport:
    from graph.investigator import bounded_network
    from investigations.evidence import build_evidence_items, deterministic_report, resolve_investigation_risk
    from patterns.matcher import match_patterns

    txn = (dag_bundle.get("evidence") or {}).get("transaction") or {"txn_id": txn_id}
    stored_risk = (dag_bundle.get("evidence") or {}).get("sender_risk") or {}
    risk = resolve_investigation_risk(txn_id, txn, stored_risk)
    network = bounded_network(txn)
    matches = match_patterns(txn, network, risk)
    evidence = build_evidence_items(txn, network, risk, matches)
    try:
        from multimodal_sof import latest_verification
        doc = latest_verification(txn_id)
        if doc:
            evidence.append(EvidenceItem(
                evidence_id="E-DOC",
                type="document_verification",
                description=(
                    f"Source-of-funds document {doc.get('verification_status')}: "
                    f"{doc.get('verification_note')}"
                ),
                source="document_verifier",
                source_ref=str(doc.get("filename") or txn_id),
                confidence=0.9 if doc.get("verification_status") == "VERIFIED_MATCH" else 0.45,
            ))
    except Exception:
        pass
    return deterministic_report(txn, evidence, matches, risk, network)


def investigate(txn_id: str, mode: str = "auto") -> dict[str, Any]:
    """Run DAG always; optionally enrich with Gemini reasoning."""
    mode = (mode or "auto").lower()
    audit.log(txn_id, "investigate_start", {"mode": mode}, actor="api")
    dag_bundle = run_dag(txn_id)
    det = dag_bundle["verdict"]

    use_gemini = mode == "gemini" or (mode == "auto" and gemini_available())
    try:
        report = _attach_platform_report(txn_id, dag_bundle, det)
    except Exception as exc:
        audit.log(txn_id, "platform_report_error", {"error": str(exc)}, actor="system")
        from investigations.evidence import deterministic_report
        report = deterministic_report(
            dag_bundle["evidence"].get("transaction") or {"txn_id": txn_id},
            [],
            [],
            dag_bundle["evidence"].get("sender_risk") or {},
            {},
        )

    if mode == "deterministic" or not use_gemini:
        if mode == "auto" and not gemini_available():
            det = {**det, "mode": "deterministic_fallback", "note": "GEMINI_API_KEY not set; used DAG verdict"}
        det = {**det, "investigation_report": report.model_dump()}
        _cache_verdict(txn_id, det, det.get("mode", "deterministic"))
        return _investigation_payload(txn_id, dag_bundle, det, report)

    try:
        txn = dag_bundle["evidence"]["transaction"]
        gem = investigate_with_gemini(txn, dag_bundle)
        try:
            report = grounded_gemini_report(
                txn,
                [EvidenceItem.model_validate(e) for e in report.supporting_evidence],
                [{"pattern_id": p, "name": p, "version": 1, "score": 1} for p in report.matched_patterns],
                dag_bundle["evidence"].get("sender_risk") or {},
                {"features": dag_bundle["evidence"].get("evidence_pack") or {}, "network_id": txn_id},
                report,
            )
        except Exception:
            pass
        merged = {
            **det,
            **gem,
            "pattern_scores": det.get("pattern_scores") or gem.get("pattern_scores"),
            "dag_risk_score": det.get("risk_score"),
            "mode": gem.get("mode", "gemini"),
            "investigation_report": report.model_dump(),
        }
    except DatabaseBusy:
        fallback = {
            **det,
            "mode": "deterministic_fallback",
            "note": "Database was busy during Gemini tool calls. Retry the investigation.",
            "investigation_report": report.model_dump(),
        }
        try:
            _cache_verdict(txn_id, fallback, "deterministic_fallback")
        except Exception:
            pass
        return _investigation_payload(txn_id, dag_bundle, fallback, report)
    except Exception as e:
        audit.log(txn_id, "gemini_error", {"error": str(e)}, actor="gemini")
        fallback = {**det, "mode": "deterministic_fallback", "note": f"Gemini failed: {e}", "investigation_report": report.model_dump()}
        try:
            _cache_verdict(txn_id, fallback, "deterministic_fallback")
        except Exception:
            pass
        return _investigation_payload(txn_id, dag_bundle, fallback, report)
    try:
        _cache_verdict(txn_id, merged, "gemini")
        audit.log(txn_id, "investigate_complete", {"mode": "gemini", "model_version": MODEL}, actor="api")
    except Exception:
        pass
    return _investigation_payload(txn_id, dag_bundle, merged, report)


def _investigation_payload(txn_id: str, dag_bundle: dict, verdict: dict, report: InvestigationReport) -> dict:
    doc = None
    try:
        from multimodal_sof import latest_verification
        doc = latest_verification(txn_id)
    except Exception:
        doc = None
    return {
        "dag": {"run_id": dag_bundle["run_id"], "trace": dag_bundle["trace"]},
        "verdict": verdict,
        "evidence": _safe_evidence(dag_bundle["evidence"]),
        "investigation_report": report.model_dump(),
        "document_verification": doc,
    }


def _safe_evidence(evidence: dict) -> dict:
    keep = [
        "transaction", "sender_profile", "receiver_profile", "sender_risk", "receiver_risk",
        "sender_sessions", "receiver_sessions", "shared_devices", "shared_beneficiaries",
        "corridor_velocity", "named_patterns", "evidence_pack",
    ]
    out = {k: evidence.get(k) for k in keep if k in evidence}
    out["neighborhood_count"] = len(evidence.get("neighborhood") or [])
    return out


def _cache_verdict(txn_id: str, verdict: dict, mode: str) -> None:
    from datetime import datetime, timezone
    con = connect()
    upsert(con, "verdicts", "txn_id", {
        "txn_id": txn_id,
        "verdict": json.dumps(verdict),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
    })
    con.commit()
    con.close()
    audit.log(txn_id, "verdict_cached", {"mode": mode, "risk_level": verdict.get("risk_level")}, actor="system")


def get_cached_verdict(txn_id: str) -> dict | None:
    con = connect()
    row = con.execute("SELECT verdict, mode, created_at FROM verdicts WHERE txn_id=?", (txn_id,)).fetchone()
    con.close()
    if not row:
        return None
    data = json.loads(row["verdict"])
    data["_cached_at"] = row["created_at"]
    data["_cached_mode"] = row["mode"]
    return data