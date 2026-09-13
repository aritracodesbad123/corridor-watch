"""Corridor Watch API — investigation console, ingest, and network intelligence."""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, ConfigDict
from auth import (
    COOKIE_NAME,
    AuthContext,
    PERMISSIONS,
    authenticate,
    get_auth_context,
    issue_session,
    public_me,
    require,
)

import agent
import audit
from config import get_settings
from db import DatabaseBusy, connect, init_schema, warmup_pool
from graph_features import network_subgraph
from investigation_dag import step_catalog
from metrics import METRICS
import phase2_sof
import phase2_memory
import phase2_mrm
import phase2_redteam
import agent_debate
import multimodal_sof
import counterfactual
import sar_generator
import rule_miner
import evaluation
from patterns.repository import seed_library, measured_library
from synthetic.showcase import describe_showcase, seed_showcase
from synthetic.world import seed_banks
import workflow

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_schema()
    phase2_memory.seed_if_empty()
    seed_banks()
    seed_library()
    seed_showcase()
    warmup_pool()
    yield


app = FastAPI(title="Corridor Watch", version="1.6.0", lifespan=lifespan)
_allowed_origins = [o.strip() for o in os.getenv("CORRIDOR_WATCH_ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=_allowed_origins, allow_methods=["GET", "POST"], allow_headers=["*"]
)


@app.exception_handler(DatabaseBusy)
async def database_busy_handler(_request, _exc):
    return JSONResponse({"detail": "database busy, retry"}, status_code=503)


@app.middleware("http")
async def no_cache_console(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path in {"/", "/index.html"} or path.endswith(".html"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


class InvestigateRequest(BaseModel):
    mode: str = Field(default="auto", description="auto | gemini | deterministic")
    force: bool = False

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value not in {"auto", "gemini", "deterministic"}:
            raise ValueError("mode must be auto, gemini, or deterministic")
        return value


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str
    notes: str = Field(default="", max_length=2000)
    # Kept for backwards compatibility with the UI; server authorization always
    # derives identity from the authenticated context.
    analyst_id: str = "analyst_demo"

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, value: str) -> str:
        allowed = {"clear", "monitor", "hold_payment", "escalate_fiu", "freeze_account"}
        if value not in allowed:
            raise ValueError(f"decision must be one of {sorted(allowed)}")
        return value


class SofRequest(BaseModel):
    explanation: str | None = None
    use_llm: bool = True


class RedteamRequest(BaseModel):
    include_llm: bool = True
    max_scenarios: int = Field(default=3, ge=1, le=10)


class CounterfactualRequest(BaseModel):
    account_age_days: int | None = Field(default=None, ge=0, le=10000)
    pass_through_ratio: float | None = Field(default=None, ge=0, le=1.5)
    avg_hold_time_minutes: float | None = Field(default=None, ge=0, le=100000)
    shared_device_count: int | None = Field(default=None, ge=0, le=1000)
    behavioral_risk: float | None = Field(default=None, ge=0, le=100)


class IngestMessage(BaseModel):
    message_id: str | None = None
    transaction: dict


class IngestBatchRequest(BaseModel):
    messages: list[IngestMessage] = Field(default_factory=list, max_length=2000)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class BenchmarkRequest(BaseModel):
    kind: str = "ingest"
    payload: dict


class WorkflowRequest(BaseModel):
    action: str
    notes: str = Field(default="", max_length=2000)

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in workflow.ACTIONS:
            raise ValueError(f"action must be one of {sorted(workflow.ACTIONS)}")
        return value


class SimulateRequest(BaseModel):
    rate: int = Field(default=8, ge=1, le=50)
    duration_seconds: int = Field(default=3600, ge=10, le=21600)
    scenario_mix: str = "live"
    force: bool = False


def _require_ingest_token(x_ingest_token: str | None = Header(default=None, alias="X-Ingest-Token")) -> None:
    expected = get_settings().ingest_token
    if expected and x_ingest_token != expected:
        raise HTTPException(401, "valid X-Ingest-Token required")


@app.get("/api/health")
def health():
    settings = get_settings()
    return {
        "ok": True,
        "gemini": agent.gemini_available(),
        "gemini_backend": agent.gemini_backend(),
        "auth_mode": "api_key" if os.getenv("CORRIDOR_WATCH_API_KEYS") else "password",
        "environment": settings.environment,
        "database": settings.dialect,
        "transaction_topic": settings.transaction_topic,
        "investigation_topic": settings.investigation_topic,
        "pubsub_push_subscription": settings.pubsub_push_subscription,
    }


@app.post("/api/auth/login")
def login(body: LoginRequest):
    user = authenticate(body.username.strip(), body.password)
    token = issue_session(user)
    ctx = AuthContext(
        analyst_id=user.get("analyst_id") or user["username"],
        role=user["role"],
        mode="password",
        display_name=user.get("display_name") or user["username"],
        permissions=tuple(sorted(PERMISSIONS.get(user["role"], set()))),
    )
    response = JSONResponse({**public_me(ctx), "token": token})
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=os.getenv("ENVIRONMENT") == "gcp",
        max_age=12 * 60 * 60,
        path="/",
    )
    return response


@app.get("/api/auth/me")
def auth_me(auth: AuthContext = Depends(get_auth_context)):
    return public_me(auth)


@app.post("/api/auth/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@app.get("/api/alerts")
def list_alerts(
    corridor: str | None = None,
    sort: str = "newest",
    auth: AuthContext = Depends(require("alerts:read")),
):
    if sort not in {"newest", "oldest", "risk"}:
        raise HTTPException(400, "sort must be newest, oldest, or risk")
    con = connect()
    rows = [dict(r) for r in con.execute(
        "SELECT txn_id, sender_id, receiver_id, amount, corridor, ts, risk_score, "
        "primary_pattern, fraud_scenario, currency, purpose, source_of_funds, "
        "risk_tier, network_id, workflow_state, showcase FROM flagged_transactions"
    ).fetchall()]
    con.close()
    rows = [r for r in rows if workflow.visible_to_role(r, auth.role)]
    if corridor:
        rows = [r for r in rows if (r.get("corridor") or "") == corridor]
    pinned = [r for r in rows if r.get("showcase")]
    rest = [r for r in rows if not r.get("showcase")]
    if sort == "risk":
        rest.sort(key=lambda r: float(r.get("risk_score") or 0), reverse=True)
    else:
        rest.sort(key=lambda r: str(r.get("ts") or ""), reverse=(sort != "oldest"))
    return (pinned + rest)[:200]


@app.get("/api/alerts/{txn_id}")
def alert_detail(txn_id: str, auth: AuthContext = Depends(require("alerts:read"))):
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
    try:
        whatif_features = counterfactual.features_for_case(txn_id)
    except Exception:
        whatif_features = {}
    return {
        "transaction": txn,
        "sender": sender,
        "receiver": receiver,
        "network": network,
        "cached_verdict": cached,
        "analyst_decisions": decisions,
        "whatif_features": whatif_features,
        "dag_steps": step_catalog(),
        "workflow_state": txn.get("workflow_state") or "open",
        "showcase": describe_showcase() if txn.get("showcase") else None,
    }


@app.post("/api/alerts/{txn_id}/investigate")
def investigate(txn_id: str, body: InvestigateRequest | None = None, auth: AuthContext = Depends(require("investigate"))):
    body = body or InvestigateRequest()
    con = connect()
    txn = con.execute(
        "SELECT * FROM flagged_transactions WHERE txn_id=?", (txn_id,)
    ).fetchone()
    if not txn:
        txn = con.execute("SELECT * FROM transactions WHERE txn_id=?", (txn_id,)).fetchone()
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
    result["document_verification"] = multimodal_sof.latest_verification(txn_id)
    return {**result, "cached": False}


@app.get("/api/alerts/{txn_id}/network")
def alert_network(txn_id: str, auth: AuthContext = Depends(require("alerts:read"))):
    return network_subgraph(txn_id)


@app.get("/api/alerts/{txn_id}/audit")
def alert_audit(txn_id: str, auth: AuthContext = Depends(require("audit:case"))):
    return audit.list_for_case(txn_id)


@app.post("/api/alerts/{txn_id}/decision")
def analyst_decision(
    txn_id: str,
    body: DecisionRequest,
    auth: AuthContext = Depends(require("decision:write")),
):
    con = connect()
    exists = con.execute(
        "SELECT 1 FROM flagged_transactions WHERE txn_id=?", (txn_id,)
    ).fetchone()
    if not exists:
        con.close()
        raise HTTPException(404, "alert not found")
    ts = datetime.now(timezone.utc).isoformat()
    analyst_id = auth.analyst_id
    if body.decision in {"hold_payment", "escalate_fiu", "freeze_account"} and auth.role == "analyst":
        raise HTTPException(403, "high-risk dispositions require FIU Team Lead authorization")
    con.execute(
        "INSERT INTO analyst_decisions (txn_id, decided_at, decision, notes, analyst_id) VALUES (?,?,?,?,?)",
        (txn_id, ts, body.decision, body.notes, analyst_id),
    )
    con.commit()
    con.close()
    audit.log(
        txn_id,
        "analyst_decision",
        {"decision": body.decision, "notes": body.notes, "analyst_id": analyst_id, "role": auth.role},
        actor=analyst_id,
        role=auth.role,
    )
    try:
        phase2_memory.remember_from_decision(txn_id, body.decision, body.notes)
    except Exception:
        pass
    extracted = None
    if body.decision in {"hold_payment", "escalate_fiu", "freeze_account"}:
        try:
            from graph.investigator import bounded_network
            from patterns.extractor import extract_from_confirmation
            c2 = connect()
            txn_row = c2.execute("SELECT * FROM flagged_transactions WHERE txn_id=?", (txn_id,)).fetchone()
            risk_row = None
            if txn_row:
                risk_row = c2.execute(
                    "SELECT * FROM risk_scores WHERE account_id=?", (txn_row["sender_id"],)
                ).fetchone()
            c2.close()
            if txn_row:
                txn_d = dict(txn_row)
                pattern = extract_from_confirmation(
                    txn_d,
                    bounded_network(txn_d),
                    dict(risk_row) if risk_row else {},
                    body.decision,
                    created_by=analyst_id,
                )
                extracted = pattern.model_dump() if pattern else None
                if extracted:
                    audit.log(
                        txn_id, "crime_pattern_extracted", extracted,
                        actor=analyst_id, role=auth.role,
                        pattern_version=f"{extracted['pattern_id']}@v{extracted['version']}",
                    )
        except Exception:
            extracted = None
    METRICS.inc("analyst_decisions_total")
    if body.decision == "clear":
        METRICS.inc("false_positive_total")
    if body.decision in {"hold_payment", "escalate_fiu", "freeze_account"}:
        METRICS.inc("confirmed_positive_total")
    try:
        wf = workflow.apply_decision(
            txn_id, body.decision, actor=analyst_id, role=auth.role, notes=body.notes
        )
    except Exception:
        wf = {"workflow_state": None}
    return {
        "ok": True,
        "decided_at": ts,
        "analyst_id": analyst_id,
        "role": auth.role,
        "crime_pattern": extracted,
        "workflow_state": wf.get("workflow_state"),
    }


@app.get("/api/alerts/{txn_id}/export", response_class=HTMLResponse)
def export_case_report(txn_id: str, auth: AuthContext = Depends(require("audit:case"))):
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
def sof_check(txn_id: str, body: SofRequest | None = None, auth: AuthContext = Depends(require("sof:run"))):
    body = body or SofRequest()
    try:
        return phase2_sof.sof_check(txn_id, body.explanation, body.use_llm)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/phase2/memory/{txn_id}")
def case_memory(txn_id: str, auth: AuthContext = Depends(require("memory:read"))):
    try:
        return phase2_memory.precedent_brief(txn_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/phase2/mrm")
def mrm_draft(auth: AuthContext = Depends(require("mrm:read"))):
    return phase2_mrm.generate_mrm_draft()


@app.post("/api/phase2/redteam")
def redteam_run(body: RedteamRequest | None = None, auth: AuthContext = Depends(require("redteam:run"))):
    body = body or RedteamRequest()
    return phase2_redteam.run_redteam(body.include_llm, body.max_scenarios)


@app.post("/api/phase2/redteam/reset")
def redteam_reset(auth: AuthContext = Depends(require("redteam:reset"))):
    return phase2_redteam.reset_redteam()


@app.get("/api/phase2/redteam")
def redteam_list(auth: AuthContext = Depends(require("mrm:read"))):
    return phase2_redteam.list_scenarios()


@app.get("/api/audit/recent")
def audit_recent(auth: AuthContext = Depends(require("audit:recent"))):
    return audit.list_recent(100)


@app.post("/api/alerts/{txn_id}/debate")
def debate_alert(txn_id: str, use_llm: bool = True, auth: AuthContext = Depends(require("debate:run"))):
    try:
        return agent_debate.run_debate(txn_id, use_llm=use_llm)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/alerts/{txn_id}/verify-document")
async def verify_doc(txn_id: str, request: Request, auth: AuthContext = Depends(require("document:verify"))):
    image_bytes = None
    mime_type = "image/png"
    filename = None
    sample_doc_name = None
    continue_analysis = False
    content_type = request.headers.get("content-type") or ""
    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            upload = form.get("file")
            if upload is not None and hasattr(upload, "read"):
                image_bytes = await upload.read()
                mime_type = getattr(upload, "content_type", None) or "application/octet-stream"
                filename = getattr(upload, "filename", None)
            sample_doc_name = form.get("sample_doc_name")
            continue_analysis = str(form.get("continue_analysis") or "").lower() in {"1", "true", "yes", "on"}
        elif content_type.startswith("application/json"):
            body = await request.json()
            sample_doc_name = body.get("sample_doc_name")
            continue_analysis = bool(body.get("continue_analysis"))
    except Exception as e:
        raise HTTPException(400, f"invalid document request: {e}") from e

    try:
        result = multimodal_sof.verify_document(
            txn_id,
            image_bytes=image_bytes,
            mime_type=mime_type,
            sample_doc_name=sample_doc_name,
            filename=filename,
        )
    except ValueError as e:
        status = 404 if "not found" in str(e) else 400
        raise HTTPException(status, str(e)) from e

    if continue_analysis:
        try:
            investigation = agent.investigate(txn_id, mode="auto")
            investigation["document_verification"] = {
                k: v for k, v in result.items() if k != "investigation"
            }
            result["investigation"] = investigation
        except Exception as e:
            result["investigation_error"] = str(e)
    return result


@app.post("/api/alerts/{txn_id}/counterfactual")
def counterfactual_sim(txn_id: str, body: CounterfactualRequest, auth: AuthContext = Depends(require("counterfactual:run"))):
    try:
        overrides = body.model_dump(exclude_unset=True)
        return counterfactual.simulate_counterfactual(txn_id, overrides)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/alerts/{txn_id}/sar")
def generate_sar_narrative(txn_id: str, jurisdiction: str = "fincen", use_llm: bool = True, auth: AuthContext = Depends(require("sar:draft"))):
    try:
        return sar_generator.generate_sar(txn_id, jurisdiction=jurisdiction, use_llm=use_llm)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/phase2/rules/mine")
def mine_rules(auth: AuthContext = Depends(require("rules:mine"))):
    return rule_miner.mine_candidate_rules()


def _decisions_for(txn_id: str) -> list[dict]:
    con = connect()
    rows = con.execute(
        "SELECT * FROM analyst_decisions WHERE txn_id=? ORDER BY id DESC", (txn_id,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


@app.get("/api/evaluation")
def evaluation_report(include_trace: bool = False, auth: AuthContext = Depends(require("audit:recent"))):
    """Deterministic benchmark scorecard; independent of Gemini availability."""
    return evaluation.run_evaluation(include_trace=include_trace)


@app.get("/api/scorecard")
def measured_scorecard(auth: AuthContext = Depends(require("command:read"))):
    return evaluation.scorecard()


@app.get("/api/showcase")
def showcase_campaign(auth: AuthContext = Depends(require("alerts:read"))):
    return describe_showcase()


@app.get("/api/workflow")
def workflow_queue(auth: AuthContext = Depends(require("alerts:read"))):
    return {"counts": workflow.counts(), "cases": workflow.queue()}


@app.post("/api/alerts/{txn_id}/workflow")
def workflow_action(
    txn_id: str,
    body: WorkflowRequest,
    auth: AuthContext = Depends(require("alerts:read")),
):
    needed = {
        "start_review": "workflow:review",
        "refer_fiu": "workflow:refer",
        "escalate": "workflow:escalate",
        "close": "workflow:close",
        "audit_ack": "workflow:audit",
    }[body.action]
    if needed not in PERMISSIONS.get(auth.role, set()):
        raise HTTPException(403, f"role '{auth.role}' cannot {body.action}")
    try:
        return workflow.apply_action(
            txn_id, body.action, actor=auth.analyst_id, role=auth.role, notes=body.notes
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(404 if "not found" in str(exc) else 400, str(exc)) from exc


@app.get("/api/metrics")
def metrics_snapshot(auth: AuthContext = Depends(require("command:read"))):
    return METRICS.snapshot()


@app.get("/api/ledger-stats")
def ledger_stats(since: str | None = None, auth: AuthContext = Depends(require("command:read"))):
    """Ledger counts for load tests. Prefer this over per-instance memory metrics."""
    con = connect()
    try:
        events = con.execute("SELECT COUNT(*) AS c FROM ingestion_events").fetchone()["c"]
        txns = con.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()["c"]
        flagged = con.execute("SELECT COUNT(*) AS c FROM flagged_transactions").fetchone()["c"]
        queued = con.execute("SELECT COUNT(*) AS c FROM investigation_queue").fetchone()["c"]
        since_events = None
        if since:
            since_events = con.execute(
                "SELECT COUNT(*) AS c FROM ingestion_events WHERE received_at>=?",
                (since,),
            ).fetchone()["c"]
    finally:
        con.close()
    return {
        "ingestion_events": int(events),
        "transactions": int(txns),
        "flagged_transactions": int(flagged),
        "investigation_queue": int(queued),
        "since": since,
        "since_ingestion_events": int(since_events) if since_events is not None else None,
        "investigation_path": "pubsub_transactions → Cloud Run → PostgreSQL investigation_queue",
    }


@app.post("/api/benchmarks")
def store_benchmark(body: BenchmarkRequest, auth: AuthContext = Depends(require("simulate:run"))):
    if body.kind not in {"ingest", "detection", "compression"}:
        raise HTTPException(400, "kind must be ingest, detection, or compression")
    evaluation.persist_benchmark(body.kind, body.payload)
    return {"ok": True, "kind": body.kind, "recorded_at": body.payload.get("measured_at")}


@app.get("/api/command-center")
def command_center(light: bool = False, auth: AuthContext = Depends(require("command:read"))):
    from graph.corridor import corridor_intelligence, investigation_compression

    flagged = high = pending = cases = 0
    wf = {}
    try:
        con = connect()
        flagged = con.execute("SELECT COUNT(*) AS c FROM flagged_transactions").fetchone()["c"]
        high = con.execute(
            "SELECT COUNT(*) AS c FROM flagged_transactions WHERE risk_score>=75"
        ).fetchone()["c"]
        pending = con.execute(
            "SELECT COUNT(*) AS c FROM investigation_queue WHERE status='pending'"
        ).fetchone()["c"]
        cases = con.execute("SELECT COUNT(*) AS c FROM investigations").fetchone()["c"]
        con.close()
        wf = workflow.counts()
    except DatabaseBusy:
        snap = METRICS.snapshot()
        settings = get_settings()
        return {
            "live_tps": snap["live_tps"],
            "session_tps": snap.get("session_tps"),
            "uptime_seconds": snap["uptime_seconds"],
            "ingestion": snap["counters"],
            "ingestion_latency_ms": snap["ingestion_latency_ms"],
            "p50_ingest_ms": (snap.get("ingestion_latency_ms") or {}).get("p50"),
            "p95_ingest_ms": (snap.get("ingestion_latency_ms") or {}).get("p95"),
            "p99_ingest_ms": (snap.get("ingestion_latency_ms") or {}).get("p99"),
            "environment": settings.environment,
            "database": settings.dialect,
            "gemini": agent.gemini_available(),
            "live_stream": _stream_status(),
            "workflow": {},
            "investigation_path": "pubsub_transactions → Cloud Run → PostgreSQL investigation_queue",
            "light": True,
            "observability_note": "database busy, retry",
        }
    snap = METRICS.snapshot()
    settings = get_settings()
    payload = {
        "live_tps": snap["live_tps"],
        "session_tps": snap.get("session_tps"),
        "uptime_seconds": snap["uptime_seconds"],
        "ingestion": snap["counters"],
        "ingestion_latency_ms": snap["ingestion_latency_ms"],
        "p50_ingest_ms": (snap.get("ingestion_latency_ms") or {}).get("p50"),
        "p95_ingest_ms": (snap.get("ingestion_latency_ms") or {}).get("p95"),
        "p99_ingest_ms": (snap.get("ingestion_latency_ms") or {}).get("p99"),
        "active_investigations": pending,
        "investigation_cases": cases,
        "high_risk_cases": high,
        "flagged_transactions": flagged,
        "environment": settings.environment,
        "database": settings.dialect,
        "gemini": agent.gemini_available(),
        "live_stream": _stream_status(),
        "workflow": wf,
        "investigation_path": "pubsub_transactions → Cloud Run → PostgreSQL investigation_queue",
        "light": light,
    }
    if light:
        return payload
    try:
        from observability import platform_signals
        from pubsub.publisher import describe_wiring
        corridors = corridor_intelligence(limit=8)
        wiring = describe_wiring()
        signals = platform_signals()
        if wiring.get("wired"):
            note = (
                f"Publishing to {wiring.get('topic')}; ingesting on {wiring.get('subscription')}."
            )
        elif settings.environment == "local":
            note = "Local ingest is in-process. Cloud Run carries the live Pub/Sub path."
        else:
            note = wiring.get("error") or "Pub/Sub status unconfirmed."
        backlog = signals.get("pubsub_backlog")
        if backlog is None:
            backlog = wiring.get("backlog")
        payload.update({
            "active_corridors": corridors,
            "suspicious_networks": investigation_compression(),
            "pubsub": wiring,
            "pubsub_backlog": backlog,
            "cloud_run_instances": signals.get("cloud_run_instances"),
            "observability_source": signals.get("source"),
            "observability_note": note,
            "showcase": describe_showcase(),
            "scorecard": evaluation.scorecard(),
        })
    except Exception as exc:
        payload["light"] = True
        payload["observability_note"] = f"Full command snapshot unavailable: {exc}"
    return payload


def _stream_status() -> dict:
    from synthetic.live_stream import STREAM
    return STREAM.status()


@app.get("/api/simulate")
def simulate_status(auth: AuthContext = Depends(require("simulate:read"))):
    return _stream_status()


@app.post("/api/simulate/start")
def simulate_start(body: SimulateRequest | None = None, auth: AuthContext = Depends(require("simulate:run"))):
    from synthetic.live_stream import STREAM
    body = body or SimulateRequest()
    return STREAM.start(
        rate=body.rate,
        duration_seconds=body.duration_seconds,
        scenario_mix=body.scenario_mix,
        force=body.force,
    )


@app.post("/api/simulate/stop")
def simulate_stop(auth: AuthContext = Depends(require("simulate:run"))):
    from synthetic.live_stream import STREAM
    return STREAM.stop()


@app.get("/api/corridors")
def list_corridors(auth: AuthContext = Depends(require("corridors:read"))):
    from graph.corridor import corridor_intelligence
    return corridor_intelligence()


@app.get("/api/patterns")
def patterns_library(auth: AuthContext = Depends(require("patterns:read"))):
    return measured_library()


@app.post("/api/alerts/{txn_id}/network-investigate")
def network_investigate(txn_id: str, auth: AuthContext = Depends(require("investigate"))):
    from investigations.service import build_investigation
    try:
        return build_investigation(txn_id, use_gemini=agent.gemini_available())
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/ingest")
def ingest_one(body: IngestMessage, _: None = Depends(_require_ingest_token)):
    from pubsub.ingestion import ingest_transaction
    from pubsub.schemas import TransactionEvent
    from pydantic import ValidationError
    try:
        event = TransactionEvent.model_validate(body.transaction)
    except ValidationError as e:
        METRICS.inc("transactions_failed_total")
        raise HTTPException(400, f"malformed transaction: {e}") from e
    return ingest_transaction(event, message_id=body.message_id, source="http")


@app.post("/api/ingest/batch")
def ingest_many(body: IngestBatchRequest, _: None = Depends(_require_ingest_token)):
    from pubsub.ingestion import ingest_batch
    from pubsub.schemas import TransactionEvent
    from pydantic import ValidationError
    events = []
    for msg in body.messages:
        try:
            events.append((TransactionEvent.model_validate(msg.transaction), msg.message_id))
        except ValidationError as e:
            METRICS.inc("transactions_failed_total")
            raise HTTPException(400, f"malformed transaction: {e}") from e
    return ingest_batch(events, source="http")


@app.post("/api/pubsub/push")
def pubsub_push(body: dict, _: None = Depends(_require_ingest_token)):
    """Google Pub/Sub push endpoint. Gemini is never called here."""
    import base64
    from pubsub.ingestion import ingest_transaction
    from pubsub.schemas import TransactionEvent
    from pydantic import ValidationError

    message = body.get("message") or {}
    message_id = message.get("messageId") or message.get("message_id")
    raw = message.get("data") or ""
    try:
        decoded = json.loads(base64.b64decode(raw).decode("utf-8")) if raw else body.get("transaction")
        event = TransactionEvent.model_validate(decoded)
    except (ValueError, ValidationError) as e:
        METRICS.inc("transactions_failed_total")
        raise HTTPException(400, f"malformed Pub/Sub message: {e}") from e
    return ingest_transaction(event, message_id=message_id, source="pubsub")


@app.get("/", include_in_schema=False)
def console():
    return FileResponse(
        "static/index.html",
        media_type="text/html",
        headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
    )


app.mount("/", StaticFiles(directory="static", html=True), name="static")
