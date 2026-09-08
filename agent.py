"""
Agentic investigation layer.

Modes:
  - deterministic: 12-step DAG only (no LLM)
  - gemini: DAG evidence + Gemini reasoning over investigation tools
  - auto: try Gemini; fall back to deterministic on missing key / errors

Provider-agnostic prompt + tool schemas; only the client SDK swaps for Azure.

IMPORTANT: uses the Interactions API (client.interactions.create), which is
Google's current documented path for function calling with Gemini 3.x models
(as of Sept 2026). The older client.models.generate_content + automatic
function calling path has repeated "missing thought_signature" bugs across
the SDK ecosystem for Gemini 3.x "thinking" models. The Interactions API
requires the caller to manage history explicitly in stateless mode (store=False):
append each returned step's model_dump() verbatim, then append a
function_result step with the tool's output, and call again. This is what
correctly preserves the thought signature — see:
https://ai.google.dev/gemini-api/docs/function-calling
https://ai.google.dev/gemini-api/docs/thought-signatures
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from db import connect
import audit
from investigation_dag import run_dag, deterministic_verdict

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
_client = None

# Set for the duration of a single investigate_with_gemini() call so the tool
# functions below can attach the right case id to their audit log entries.
_CURRENT_TXN_ID: str | None = None


def gemini_available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def client():
    global _client
    if _client is None:
        from google import genai
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
Ground every claim in tool data. Do not invent counterparties, amounts, or devices."""


def _call_with_retry(c, **kwargs):
    from google.genai import errors as genai_errors
    delays = [1, 2]
    for attempt, delay in enumerate([0] + delays):
        if delay:
            time.sleep(delay)
        try:
            return c.interactions.create(**kwargs)
        except genai_errors.ServerError as e:
            if "UNAVAILABLE" not in str(e) or attempt == len(delays):
                raise


def _parse_verdict(text: str, fallback_score: float) -> dict:
    text = (text or "").strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
        data.setdefault("mode", "gemini")
        return data
    except json.JSONDecodeError:
        return {
            "risk_level": "unknown",
            "risk_score": int(fallback_score),
            "primary_pattern": "parse_error",
            "rationale": text[:400],
            "recommended_action": "manual review",
            "mode": "gemini_parse_error",
        }


def investigate_with_gemini(txn: dict, dag_bundle: dict | None = None) -> dict:
    global _CURRENT_TXN_ID
    c = client()
    payload = {"transaction": txn}
    if dag_bundle:
        payload["dag_deterministic_verdict"] = dag_bundle.get("verdict")
        payload["dag_evidence_keys"] = list((dag_bundle.get("evidence") or {}).keys())

    txn_id = txn.get("txn_id", "")
    _CURRENT_TXN_ID = txn_id
    tools = _tool_declarations()

    # Stateless mode (store=False): we own the full history and must append
    # each returned step verbatim (step.model_dump()) before the next call —
    # this is what preserves the thought_signature correctly for Gemini 3.x.
    history = [{
        "type": "user_input",
        "content": [{"type": "text", "text": SYSTEM_PROMPT + "\n\n" + json.dumps(payload, default=str)}],
    }]

    try:
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


def investigate(txn_id: str, mode: str = "auto") -> dict[str, Any]:
    """Run DAG always; optionally enrich with Gemini reasoning."""
    mode = (mode or "auto").lower()
    audit.log(txn_id, "investigate_start", {"mode": mode}, actor="api")
    dag_bundle = run_dag(txn_id)
    det = dag_bundle["verdict"]

    use_gemini = mode == "gemini" or (mode == "auto" and gemini_available())
    if mode == "deterministic" or not use_gemini:
        if mode == "auto" and not gemini_available():
            det = {**det, "mode": "deterministic_fallback", "note": "GEMINI_API_KEY not set; used DAG verdict"}
        _cache_verdict(txn_id, det, det.get("mode", "deterministic"))
        return {"dag": {"run_id": dag_bundle["run_id"], "trace": dag_bundle["trace"]}, "verdict": det, "evidence": _safe_evidence(dag_bundle["evidence"])}

    try:
        txn = dag_bundle["evidence"]["transaction"]
        gem = investigate_with_gemini(txn, dag_bundle)
        merged = {
            **det,
            **gem,
            "pattern_scores": det.get("pattern_scores") or gem.get("pattern_scores"),
            "dag_risk_score": det.get("risk_score"),
            "mode": gem.get("mode", "gemini"),
        }
        _cache_verdict(txn_id, merged, "gemini")
        audit.log(txn_id, "investigate_complete", {"mode": "gemini"}, actor="api")
        return {"dag": {"run_id": dag_bundle["run_id"], "trace": dag_bundle["trace"]}, "verdict": merged, "evidence": _safe_evidence(dag_bundle["evidence"])}
    except Exception as e:
        audit.log(txn_id, "gemini_error", {"error": str(e)}, actor="gemini")
        fallback = {**det, "mode": "deterministic_fallback", "note": f"Gemini failed: {e}"}
        _cache_verdict(txn_id, fallback, "deterministic_fallback")
        return {"dag": {"run_id": dag_bundle["run_id"], "trace": dag_bundle["trace"]}, "verdict": fallback, "evidence": _safe_evidence(dag_bundle["evidence"])}


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
    con = connect(row_factory=False)
    con.execute(
        "INSERT OR REPLACE INTO verdicts (txn_id, verdict, created_at, mode) VALUES (?,?,?,?)",
        (txn_id, json.dumps(verdict), datetime.now(timezone.utc).isoformat(), mode),
    )
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