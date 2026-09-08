"""Corridor Watch API — Phase 1 investigation console + Phase 2 judgment endpoints."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import agent
import audit
from db import connect, init_schema
from graph_features import network_subgraph
from investigation_dag import step_catalog
import phase2_sof
import phase2_memory
import phase2_mrm
import phase2_redteam
import agent_debate
import multimodal_sof
import counterfactual
import sar_generator
import rule_miner

app = FastAPI(title="Corridor Watch", version="1.3.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


def get_auth_context(
    x_analyst_id: str | None = Header(default="analyst_demo", alias="X-Analyst-ID"),
    x_analyst_role: str | None = Header(default="analyst", alias="X-Analyst-Role"),
) -> dict:
    return {"analyst_id": x_analyst_id or "analyst_demo", "role": x_analyst_role or "analyst"}


class InvestigateRequest(BaseModel):
    mode: str = Field(default="auto", description="auto | gemini | deterministic")
    force: bool = False


class DecisionRequest(BaseModel):
    decision: str
    notes: str = ""
    analyst_id: str = "analyst_demo"


class SofRequest(BaseModel):
    explanation: str | None = None
    use_llm: bool = True


class RedteamRequest(BaseModel):
    include_llm: bool = True
    max_scenarios: int = 3


class CounterfactualRequest(BaseModel):
    account_age_days: int | None = None
    pass_through_ratio: float | None = None
    avg_hold_time_minutes: float | None = None
    shared_device_count: int | None = None
    behavioral_risk: float | None = None


class DocVerifyRequest(BaseModel):
    sample_doc_name: str | None = None


@app.on_event("startup")
def startup():
    init_schema()
    phase2_memory.seed_if_empty()


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "gemini": agent.gemini_available(),
        "phases": ["1", "2"],
    }


@app.get("/api/alerts")
def list_alerts():
    con = connect()
    rows = con.execute(
        "SELECT * FROM flagged_transactions ORDER BY risk_score DESC LIMIT 150"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


@app.get("/api/alerts/{txn_id}")
def alert_detail(txn_id: str):
    con = connect()
    txn = con.execute(
        "SELECT * FROM flagged_transactions WHERE txn_id=?", (txn_id,)
    ).fetchone()
    if not txn:
        con.close()
        raise HTTPException(404, "alert not found")
    txn = dict(txn)
    con.close()
    sender = agent.get_account_context(txn["sender_id"])
    receiver = agent.get_account_context(txn["receiver_id"])
    network = network_subgraph(txn_id)
    cached = agent.get_cached_verdict(txn_id)
    decisions = _decisions_for(txn_id)
    return {
        "transaction": txn,
        "sender": sender,
        "receiver": receiver,
        "network": network,
        "cached_verdict": cached,
        "analyst_decisions": decisions,
        "dag_steps": step_catalog(),
    }


@app.post("/api/alerts/{txn_id}/investigate")
def investigate(txn_id: str, body: InvestigateRequest | None = None):
    body = body or InvestigateRequest()
    con = connect()
    txn = con.execute(
        "SELECT * FROM flagged_transactions WHERE txn_id=?", (txn_id,)
    ).fetchone()
    con.close()
    if not txn:
        raise HTTPException(404, "alert not found")

    if not body.force:
        cached = agent.get_cached_verdict(txn_id)
        if cached and body.mode == "auto":
            return {"verdict": cached, "cached": True, "dag": None, "evidence": None}

    try:
        result = agent.investigate(txn_id, mode=body.mode)
    except Exception as e:
        raise HTTPException(500, f"Investigation failed: {e}") from e
    return {**result, "cached": False}


@app.get("/api/alerts/{txn_id}/network")
def alert_network(txn_id: str):
    return network_subgraph(txn_id)


@app.get("/api/alerts/{txn_id}/audit")
def alert_audit(txn_id: str):
    return audit.list_for_case(txn_id)


@app.post("/api/alerts/{txn_id}/decision")
def analyst_decision(
    txn_id: str,
    body: DecisionRequest,
    auth: dict = Depends(get_auth_context),
):
    con = connect()
    exists = con.execute(
        "SELECT 1 FROM flagged_transactions WHERE txn_id=?", (txn_id,)
    ).fetchone()
    if not exists:
        con.close()
        raise HTTPException(404, "alert not found")
    ts = datetime.now(timezone.utc).isoformat()
    analyst_id = body.analyst_id if body.analyst_id != "analyst_demo" else auth["analyst_id"]
    con.execute(
        "INSERT INTO analyst_decisions (txn_id, decided_at, decision, notes, analyst_id) VALUES (?,?,?,?,?)",
        (txn_id, ts, body.decision, body.notes, analyst_id),
    )
    con.commit()
    con.close()
    audit.log(
        txn_id,
        "analyst_decision",
        {"decision": body.decision, "notes": body.notes, "analyst_id": analyst_id, "role": auth["role"]},
        actor=analyst_id,
    )
    try:
        phase2_memory.remember_from_decision(txn_id, body.decision, body.notes)
    except Exception:
        pass
    return {"ok": True, "decided_at": ts, "analyst_id": analyst_id, "role": auth["role"]}


@app.get("/api/alerts/{txn_id}/export", response_class=HTMLResponse)
def export_case_report(txn_id: str):
    con = connect()
    txn = con.execute("SELECT * FROM flagged_transactions WHERE txn_id=?", (txn_id,)).fetchone()
    if not txn:
        con.close()
        raise HTTPException(404, "alert not found")
    txn = dict(txn)
    verdict = agent.get_cached_verdict(txn_id) or {}
    decisions = _decisions_for(txn_id)
    events = audit.list_for_case(txn_id)
    sender = agent.get_account_context(txn["sender_id"])
    receiver = agent.get_account_context(txn["receiver_id"])
    con.close()

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>Case Audit Package — {txn_id}</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; margin: 36px; color: #111; line-height: 1.5; background: #fff; }}
  h1 {{ border-bottom: 2px solid #222; padding-bottom: 8px; font-size: 22px; margin-bottom: 4px; }}
  .subhead {{ font-size: 12px; color: #666; font-family: monospace; margin-bottom: 24px; }}
  h2 {{ color: #222; font-size: 15px; margin-top: 24px; border-bottom: 1px solid #ccc; padding-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .box {{ background: #f8f9fa; border: 1px solid #e9ecef; padding: 14px 18px; border-radius: 6px; margin: 12px 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }}
  th, td {{ border: 1px solid #dee2e6; padding: 8px 12px; text-align: left; }}
  th {{ background: #e9ecef; font-weight: 600; }}
  .badge {{ background: #0F1419; color: #3FA796; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-family: monospace; }}
</style>
</head>
<body>
  <h1>Corridor Watch — Official Case Audit Package</h1>
  <div class="subhead">CROSS-BORDER COMPLIANCE INVESTIGATION RECORD · {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}</div>

  <div class="box">
    <p><b>Case ID:</b> <span class="badge">{txn_id}</span> &nbsp;|&nbsp; <b>Amount:</b> ${txn['amount']:,.2f} {txn.get('currency', 'USD')} &nbsp;|&nbsp; <b>Corridor:</b> {txn['corridor']}</p>
    <p><b>Sender:</b> {txn['sender_id']} ({sender.get('profile', {}).get('country', 'N/A')}) &nbsp;&rarr;&nbsp; <b>Receiver:</b> {txn['receiver_id']} ({receiver.get('profile', {}).get('country', 'N/A')})</p>
    <p><b>Primary Fraud Pattern:</b> {txn.get('primary_pattern', 'N/A')} &nbsp;|&nbsp; <b>Risk Score:</b> {txn.get('risk_score', 'N/A')}</p>
    <p><b>Declared Purpose:</b> {txn.get('purpose', 'N/A')} &nbsp;|&nbsp; <b>Declared Source of Funds:</b> {txn.get('source_of_funds', 'N/A')}</p>
  </div>

  <h2>Investigation Verdict</h2>
  <div class="box">
    <p><b>Risk Level:</b> {verdict.get('risk_level', 'Pending')} &nbsp;|&nbsp; <b>Score:</b> {verdict.get('risk_score', 'N/A')} &nbsp;|&nbsp; <b>Mode:</b> {verdict.get('mode', 'N/A')}</p>
    <p><b>Rationale:</b> {verdict.get('rationale', 'No verdict logged yet.')}</p>
    <p><b>Recommended Directive:</b> {verdict.get('recommended_action', 'N/A')}</p>
  </div>

  <h2>Analyst Dispositions & History</h2>
  <table>
    <thead><tr><th>Timestamp</th><th>Analyst ID</th><th>Decision</th><th>Notes</th></tr></thead>
    <tbody>
      {''.join(f"<tr><td>{d['decided_at']}</td><td>{d['analyst_id']}</td><td><b>{d['decision']}</b></td><td>{d['notes']}</td></tr>" for d in decisions) or '<tr><td colspan="4">No analyst decisions recorded yet.</td></tr>'}
    </tbody>
  </table>

  <h2>Audit Log Trail</h2>
  <table>
    <thead><tr><th>Timestamp</th><th>Actor</th><th>Event Type</th><th>Detail</th></tr></thead>
    <tbody>
      {''.join(f"<tr><td>{e['ts']}</td><td>{e['actor']}</td><td>{e['event_type']}</td><td>{e['detail'][:140]}</td></tr>" for e in events) or '<tr><td colspan="4">No audit log entries.</td></tr>'}
    </tbody>
  </table>

  <p style="margin-top: 40px; font-size: 11px; color: #888; text-anchor: middle; text-align: center;">Generated by Corridor Watch investigation engine — confidential compliance audit artifact.</p>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.post("/api/phase2/sof/{txn_id}")
def sof_check(txn_id: str, body: SofRequest | None = None):
    body = body or SofRequest()
    try:
        return phase2_sof.sof_check(txn_id, body.explanation, body.use_llm)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/phase2/memory/{txn_id}")
def case_memory(txn_id: str):
    try:
        return phase2_memory.precedent_brief(txn_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/phase2/mrm")
def mrm_draft():
    return phase2_mrm.generate_mrm_draft()


@app.post("/api/phase2/redteam")
def redteam_run(body: RedteamRequest | None = None):
    body = body or RedteamRequest()
    return phase2_redteam.run_redteam(body.include_llm, body.max_scenarios)


@app.post("/api/phase2/redteam/reset")
def redteam_reset():
    return phase2_redteam.reset_redteam()


@app.get("/api/phase2/redteam")
def redteam_list():
    return phase2_redteam.list_scenarios()


@app.get("/api/audit/recent")
def audit_recent():
    return audit.list_recent(100)


@app.post("/api/alerts/{txn_id}/debate")
def debate_alert(txn_id: str, use_llm: bool = True):
    try:
        return agent_debate.run_debate(txn_id, use_llm=use_llm)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/alerts/{txn_id}/verify-document")
def verify_doc(txn_id: str, body: DocVerifyRequest | None = None):
    body = body or DocVerifyRequest()
    try:
        return multimodal_sof.verify_document(txn_id, sample_doc_name=body.sample_doc_name)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/alerts/{txn_id}/counterfactual")
def counterfactual_sim(txn_id: str, body: CounterfactualRequest):
    try:
        overrides = body.dict(exclude_unset=True)
        return counterfactual.simulate_counterfactual(txn_id, overrides)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/alerts/{txn_id}/sar")
def generate_sar_narrative(txn_id: str, jurisdiction: str = "fincen", use_llm: bool = True):
    try:
        return sar_generator.generate_sar(txn_id, jurisdiction=jurisdiction, use_llm=use_llm)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/phase2/rules/mine")
def mine_rules():
    return rule_miner.mine_candidate_rules()


def _decisions_for(txn_id: str) -> list[dict]:
    con = connect()
    rows = con.execute(
        "SELECT * FROM analyst_decisions WHERE txn_id=? ORDER BY id DESC", (txn_id,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


app.mount("/", StaticFiles(directory="static", html=True), name="static")
