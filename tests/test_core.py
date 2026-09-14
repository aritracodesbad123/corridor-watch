import json
import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from db import connect, init_schema
from evaluation import run_evaluation
from graph_features import composite_score, pattern_scores


def test_pattern_scores_are_bounded():
    features = {
        "account_age_days": 2,
        "pass_through_ratio": 1.0,
        "fan_in_count": 12,
        "avg_hold_time_minutes": 20,
        "shared_device_count": 5,
        "shared_beneficiary_count": 4,
        "multi_hop_chain_depth": 4,
        "corridor_velocity_score": 5,
        "behavioral_risk": 90,
    }
    patterns = pattern_scores(features, {"stated_income_usd": 1000, "occupation": "Student"})
    assert patterns
    assert all(0 <= v <= 100 for v in patterns.values())
    score, primary = composite_score(features, patterns)
    assert 0 <= score <= 100
    assert primary in patterns


def test_schema_bootstrap_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    import db
    monkeypatch.setattr(db, "DB_PATH", db_path)
    init_schema()
    init_schema()
    con = connect()
    tables = {r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert "transactions" in tables
    assert "audit_log" in tables


def test_evaluation_on_generated_dataset(monkeypatch, tmp_path):
    # Use the repository's generated demo DB; this is an integration-style smoke test.
    from db import DB_PATH
    assert DB_PATH.exists()
    result = run_evaluation()
    assert result["status"] == "ok"
    assert result["sample_count"] > 0
    assert 0 <= result["metrics"]["precision"] <= 1
    assert 0 <= result["metrics"]["recall"] <= 1


def test_decision_labels_are_not_free_form():
    from main import DecisionRequest
    with pytest.raises(Exception):
        DecisionRequest(decision="delete_database")


def test_rbac_blocks_privileged_endpoint():
    from main import app
    client = TestClient(app)
    denied = client.get("/api/phase2/mrm", headers={"X-Analyst-Role": "analyst"})
    assert denied.status_code == 403
    allowed = client.get("/api/phase2/mrm", headers={"X-Analyst-Role": "mrm_auditor"})
    assert allowed.status_code == 200


def test_thinking_off_sets_budget_zero():
    from agent import MODEL, _thinking_off
    cfg = _thinking_off()
    assert cfg is not None
    assert cfg.include_thoughts is False
    if str(MODEL).startswith("gemini-3"):
        assert str(cfg.thinking_level).endswith("MINIMAL")
    else:
        assert cfg.thinking_budget == 0


def test_investigate_gemini_is_one_call(monkeypatch):
    import agent
    from investigations.schemas import InvestigationReport, EvidenceItem

    seen = {"tool": 0, "grounded": 0}
    fb = InvestigationReport(
        investigation_summary="summary",
        risk_hypothesis="hyp",
        supporting_evidence=[EvidenceItem(evidence_id="E-TXN", type="txn", description="wire", source="ledger")],
        recommended_disposition="monitor",
        confidence=40,
        uncertainty="u",
        gemini_used=True,
    )

    monkeypatch.setattr(agent, "gemini_available", lambda: True)
    monkeypatch.setattr(agent, "run_dag", lambda txn_id, **k: {
        "run_id": "run",
        "trace": [],
        "evidence": {"transaction": {"txn_id": txn_id, "sender_id": "A", "receiver_id": "B"}, "sender_risk": {}},
        "verdict": {
            "risk_level": "medium",
            "risk_score": 50,
            "primary_pattern": "elevated_activity",
            "rationale": "dag",
            "recommended_action": "review",
            "mode": "deterministic",
        },
    })
    monkeypatch.setattr(agent, "_attach_platform_report", lambda *a, **k: fb)
    monkeypatch.setattr(agent, "investigate_with_gemini", lambda *a, **k: seen.__setitem__("tool", seen["tool"] + 1) or {"mode": "gemini"})
    monkeypatch.setattr(agent, "grounded_gemini_report", lambda *a, **k: seen.__setitem__("grounded", seen["grounded"] + 1) or fb)
    monkeypatch.setattr(agent, "_cache_verdict", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_investigation_payload", lambda *a, **k: {"ok": True})
    import audit as audit_mod
    monkeypatch.setattr(audit_mod, "log", lambda *a, **k: None)

    out = agent.investigate("T-1", mode="gemini")
    assert out == {"ok": True}
    assert seen == {"tool": 0, "grounded": 1}


def test_rbac_uses_server_identity_for_decisions():
    from main import app
    from db import connect
    txn_row = connect().execute("SELECT txn_id FROM flagged_transactions LIMIT 1").fetchone()
    assert txn_row is not None, "demo dataset must contain derived flagged transactions"
    txn = txn_row[0]
    client = TestClient(app)
    response = client.post(
        f"/api/alerts/{txn}/decision",
        headers={"X-Analyst-Role": "fiu_lead", "X-Analyst-ID": "lead_real"},
        json={"decision": "monitor", "analyst_id": "attacker"},
    )
    assert response.status_code == 200
    assert response.json()["analyst_id"] == "lead_real"
