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
