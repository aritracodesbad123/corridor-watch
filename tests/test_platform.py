"""Platform tests for ingest, risk tiers, Crime Pattern DNA, RBAC, and grounded reports."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from config import reset_settings_cache
from db import connect, init_schema
from investigations.evidence import build_evidence_items, deterministic_report
from investigations.schemas import InvestigationReport
from patterns.extractor import extract_from_confirmation
from patterns.matcher import match_patterns
from patterns.repository import seed_library
from pubsub.ingestion import ingest_transaction
from pubsub.schemas import TransactionEvent
from risk.tiers import RiskTier, assign_tier, cheap_screen


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    import db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "platform.db")
    reset_settings_cache()
    init_schema()
    seed_library()
    yield
    reset_settings_cache()


def _event(**overrides) -> TransactionEvent:
    base = {
        "txn_id": "T-TEST-1",
        "timestamp": "2026-09-01T12:00:00+00:00",
        "sender_account_id": "A-SEND",
        "receiver_account_id": "A-RECV",
        "amount": 250.0,
        "origin_country": "IN",
        "destination_country": "SG",
        "origin_bank_id": "BANK_IN",
        "destination_bank_id": "BANK_SG",
    }
    base.update(overrides)
    return TransactionEvent.model_validate(base)


def test_risk_tiers_are_configurable(monkeypatch):
    monkeypatch.setenv("RISK_THRESHOLD_LOW", "10")
    monkeypatch.setenv("RISK_THRESHOLD_MEDIUM", "20")
    monkeypatch.setenv("RISK_THRESHOLD_HIGH", "30")
    reset_settings_cache()
    assert assign_tier(5) is RiskTier.LOW
    assert assign_tier(15) is RiskTier.MEDIUM
    assert assign_tier(25) is RiskTier.HIGH
    assert assign_tier(90) is RiskTier.CRITICAL
    reset_settings_cache()


def test_cheap_screen_never_needs_gemini():
    result = cheap_screen(_event(amount=9000, account_age_days=2).model_dump())
    assert result.tier in RiskTier
    assert "high_value" in result.signals
    assert "new_account" in result.signals


def test_malformed_transaction_rejected():
    with pytest.raises(ValidationError):
        TransactionEvent.model_validate({"txn_id": "X", "amount": -1})


def test_ingest_is_idempotent(isolated_db):
    event = _event(txn_id="T-DUP-1", amount=12000, account_age_days=3)
    first = ingest_transaction(event, message_id="m-1", source="test")
    second = ingest_transaction(event, message_id="m-1", source="test")
    third = ingest_transaction(event, message_id="m-2", source="test")
    assert first["duplicate"] is False
    assert first["gemini_invoked"] is False
    assert second["duplicate"] is True
    assert third["duplicate"] is True
    con = connect()
    n = con.execute("SELECT COUNT(*) AS c FROM transactions WHERE txn_id='T-DUP-1'").fetchone()["c"]
    con.close()
    assert n == 1


def test_high_value_ingest_queues_investigation(isolated_db):
    result = ingest_transaction(
        _event(txn_id="T-HOT", amount=15000, account_age_days=1, fraud_scenario="mule_pass_through"),
        message_id="m-hot",
    )
    assert result["queued_for_investigation"] is True
    assert result["risk_tier"] in {"HIGH", "CRITICAL"}
    con = connect()
    queued = con.execute("SELECT status FROM investigation_queue WHERE txn_id='T-HOT'").fetchone()
    con.close()
    assert queued is not None
    assert queued["status"] == "QUEUED"


def test_pattern_dna_match_returns_evidence(isolated_db):
    txn = {"txn_id": "T1", "sender_id": "A", "receiver_id": "B", "corridor": "IN->SG", "fraud_scenario": "mule_pass_through"}
    network = {
        "features": {
            "fan_in": 6, "fan_out": 2, "shared_device_groups": 1,
            "shared_beneficiary_groups": 1, "cross_border": 3, "institution_count": 3, "txn_count": 8,
        }
    }
    matches = match_patterns(
        txn, network,
        {"account_age_days": 3, "pass_through_ratio": 0.95, "avg_hold_time_minutes": 20},
        persist=False,
    )
    assert matches
    assert matches[0]["evidence"]
    assert "match_strength" in matches[0]
    assert matches[0]["matched_signals"]
    assert "missing_signals" in matches[0]
    assert all("evidence_id" in e for e in matches[0]["evidence"])
    con = connect()
    stored = con.execute("SELECT COUNT(*) AS c FROM pattern_matches WHERE txn_id='T1'").fetchone()["c"]
    con.close()
    assert stored == 0


def test_confirmed_decision_extracts_or_reinforces_pattern(isolated_db):
    txn = {"txn_id": "T-CONF", "sender_id": "A", "receiver_id": "B", "corridor": "JP->SG", "fraud_scenario": "mule_pass_through"}
    network = {"features": {"fan_in": 5, "txn_count": 6, "cross_border": 2, "shared_device_groups": 1, "institution_count": 2}}
    pattern = extract_from_confirmation(txn, network, {"account_age_days": 2}, "escalate_fiu", created_by="lead_test")
    assert pattern is not None
    cleared = extract_from_confirmation(txn, network, {}, "clear", created_by="lead_test")
    assert cleared is None


def test_report_confidence_varies_with_evidence(isolated_db):
    from investigations.evidence import _confidence_for_case
    thin = _confidence_for_case(63, [], [], {"features": {"txn_count": 1}}, {"risk_source": "screen_only"})
    rich = _confidence_for_case(
        63,
        [type("E", (), {"evidence_id": "E-TXN", "description": "x"})(),
         type("E", (), {"evidence_id": "E-NET", "description": "x"})(),
         type("E", (), {"evidence_id": "E-DOC", "description": "AMOUNT_DISCREPANCY"})()],
        [{"score": 0.8}],
        {"features": {"txn_count": 8}},
        {"risk_source": "live_neighborhood", "pass_through_ratio": 1.0, "account_age_days": 2},
    )
    assert thin != rich
    assert thin < rich


def test_grounded_report_schema(isolated_db):
    txn = {"txn_id": "T1", "sender_id": "A", "receiver_id": "B", "amount": 1000, "currency": "USD", "corridor": "IN->SG"}
    network = {"network_id": "N-1", "features": {"txn_count": 4, "account_count": 5, "institution_count": 2}}
    evidence = build_evidence_items(txn, network, {"risk_score": 80, "primary_pattern": "mule_pass_through"}, [])
    report = deterministic_report(txn, evidence, [], {"risk_score": 80}, network)
    parsed = InvestigationReport.model_validate(report.model_dump())
    assert parsed.gemini_used is False
    assert parsed.supporting_evidence
    assert parsed.alternative_explanations
    assert parsed.recommended_disposition == "escalate_fiu"
    hold = deterministic_report(txn, evidence, [], {"risk_score": 43}, network)
    assert hold.recommended_disposition == "hold_payment"


def test_high_risk_decision_still_requires_fiu_lead():
    from main import app
    client = TestClient(app)
    denied = client.post(
        "/api/alerts/does-not-matter/decision",
        headers={"X-Analyst-Role": "analyst", "X-Analyst-ID": "a1"},
        json={"decision": "freeze_account", "notes": "no"},
    )
    assert denied.status_code in {403, 404}


def test_command_center_requires_auth_role():
    from main import app
    client = TestClient(app)
    res = client.get("/api/command-center", headers={"X-Analyst-Role": "analyst"})
    assert res.status_code == 200
    body = res.json()
    assert "live_tps" in body
    assert body["pubsub_backlog"] is None
    assert body["pubsub"]["wired"] is False
    assert "PostgreSQL investigation_queue" in body["investigation_path"]
    assert body["pubsub"]["investigation_topic_role"].startswith("optional fan-out")


def test_ingest_http_validates_and_dedupes(isolated_db, monkeypatch):
    import db as dbmod
    monkeypatch.setattr("db.DB_PATH", dbmod.DB_PATH)
    from main import app
    client = TestClient(app)
    payload = {
        "message_id": "http-1",
        "transaction": _event(txn_id="T-HTTP-1", amount=9000, account_age_days=2).model_dump(),
    }
    first = client.post("/api/ingest", json=payload)
    second = client.post("/api/ingest", json=payload)
    assert first.status_code == 200
    assert first.json()["duplicate"] is False
    assert first.json()["gemini_invoked"] is False
    assert second.json()["duplicate"] is True


def test_live_stream_start_stop_and_flags(isolated_db):
    from synthetic.live_stream import LiveStream
    stream = LiveStream()
    started = stream.start(rate=5, duration_seconds=10, scenario_mix="live", force=True)
    assert started["running"] is True
    assert started["gemini_invoked"] is False
    time.sleep(1.2)
    status = stream.status()
    stream.stop()
    assert status["accepted"] >= 1
    assert stream.status()["running"] is False
    assert stream.status()["transport"] == "in_process"
    public = stream.public_status()
    assert public["queued_for_investigation"] >= 0
    assert public["count_source"] in {"ledger", "in_memory"}


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _seed_case(txn_id="T-DOC-1", *, sparse_risk=False):
    from db import connect, upsert
    con = connect(row_factory=False)
    upsert(con, "flagged_transactions", "txn_id", {
        "txn_id": txn_id,
        "sender_id": "A-SEND",
        "receiver_id": "A-RECV",
        "amount": 1000.0,
        "corridor": "IN-SG",
        "ts": "2026-09-01T12:00:00+00:00",
        "risk_score": 72,
        "primary_pattern": "elevated_activity",
        "fraud_scenario": "",
        "currency": "USD",
        "purpose": "invoice settlement",
        "source_of_funds": "trade",
    })
    upsert(con, "transactions", "txn_id", {
        "txn_id": txn_id,
        "sender_id": "A-SEND",
        "receiver_id": "A-RECV",
        "amount": 1000.0,
        "corridor": "IN-SG",
        "ts": "2026-09-01T12:00:00+00:00",
        "currency": "USD",
        "purpose": "invoice settlement",
        "source_of_funds": "trade",
        "fraud_scenario": "",
    })
    if sparse_risk:
        upsert(con, "risk_scores", "account_id", {
            "account_id": "A-SEND",
            "risk_score": 72,
            "fan_in_count": None,
            "pass_through_ratio": None,
            "avg_hold_time_minutes": None,
            "shared_device_count": None,
            "account_age_days": None,
            "behavioral_risk": None,
            "primary_pattern": "elevated_activity",
        })
    con.commit()
    con.close()


def test_document_upload_then_continues_analysis(isolated_db):
    from main import app
    _seed_case("T-DOC-1")
    client = TestClient(app)
    headers = {"X-Analyst-Role": "analyst"}
    res = client.post(
        "/api/alerts/T-DOC-1/verify-document",
        headers=headers,
        files={"file": ("invoice.png", PNG_1X1, "image/png")},
        data={"continue_analysis": "true"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["txn_id"] == "T-DOC-1"
    assert body["used_upload"] is True
    assert body["filename"] == "invoice.png"
    assert "investigation" in body
    assert body["investigation"]["verdict"]["risk_score"] is not None
    assert body["investigation"]["document_verification"]["used_upload"] is True


def test_document_json_verify_still_works(isolated_db):
    from main import app
    _seed_case("T-DOC-2")
    client = TestClient(app)
    res = client.post(
        "/api/alerts/T-DOC-2/verify-document",
        headers={"X-Analyst-Role": "analyst"},
        json={"sample_doc_name": "invoice"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["used_upload"] is False
    assert body["verification_status"] in {"VERIFIED_MATCH", "AMOUNT_DISCREPANCY", "UNVERIFIED_FORMAT"}


def test_counterfactual_works_with_sparse_risk(isolated_db):
    from main import app
    _seed_case("T-WHATIF-1", sparse_risk=True)
    client = TestClient(app)
    res = client.post(
        "/api/alerts/T-WHATIF-1/counterfactual",
        headers={"X-Analyst-Role": "analyst"},
        json={"account_age_days": 365, "pass_through_ratio": 0.1, "shared_device_count": 0},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "baseline" in body
    assert "counterfactual" in body
    assert "account_age_days" in body["counterfactual"]["applied_overrides"]
    # Live / sparse accounts must not collapse to the old dummy composite (22).
    assert body["feature_source"] == "live_neighborhood"
    assert body["baseline"]["risk_score"] != 22


def test_password_login_and_alert_sort(isolated_db, monkeypatch):
    from main import app
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv(
        "CORRIDOR_WATCH_USERS",
        '{"auth_secret":"test-secret","users":[{"username":"analyst","password":"pw-a","role":"analyst","display_name":"Analyst"},{"username":"lead","password":"pw-l","role":"fiu_lead","display_name":"Lead"}]}',
    )
    client = TestClient(app)
    denied = client.get("/api/alerts")
    assert denied.status_code == 401
    bad = client.post("/api/auth/login", json={"username": "analyst", "password": "nope"})
    assert bad.status_code == 401
    ok = client.post("/api/auth/login", json={"username": "analyst", "password": "pw-a"})
    assert ok.status_code == 200
    assert ok.json()["role"] == "analyst"
    token = ok.json()["token"]
    alerts = client.get("/api/alerts?sort=newest", headers={"Authorization": f"Bearer {token}"})
    assert alerts.status_code == 200
    lead = client.post("/api/auth/login", json={"username": "lead", "password": "pw-l"})
    assert lead.json()["role"] == "fiu_lead"


def test_showcase_and_workflow(isolated_db):
    from main import app
    from synthetic.showcase import HERO_TXN_ID, seed_showcase

    seeded = seed_showcase()
    assert seeded["hero_txn_id"] == HERO_TXN_ID
    client = TestClient(app)
    show = client.get("/api/showcase", headers={"X-Analyst-Role": "analyst"})
    assert show.status_code == 200
    assert show.json()["hero_txn_id"] == HERO_TXN_ID
    review = client.post(
        f"/api/alerts/{HERO_TXN_ID}/workflow",
        headers={"X-Analyst-Role": "analyst"},
        json={"action": "start_review", "notes": "opened Lotus Ring"},
    )
    assert review.status_code == 200, review.text
    assert review.json()["workflow_state"] == "analyst_review"
    forbidden = client.post(
        f"/api/alerts/{HERO_TXN_ID}/workflow",
        headers={"X-Analyst-Role": "analyst"},
        json={"action": "escalate", "notes": "need lead"},
    )
    assert forbidden.status_code == 403
    escalate = client.post(
        f"/api/alerts/{HERO_TXN_ID}/workflow",
        headers={"X-Analyst-Role": "fiu_lead"},
        json={"action": "escalate", "notes": "cross-bank mule"},
    )
    assert escalate.status_code == 200
    assert escalate.json()["workflow_state"] == "escalated_fiu"
    audit_ack = client.post(
        f"/api/alerts/{HERO_TXN_ID}/workflow",
        headers={"X-Analyst-Role": "mrm_auditor"},
        json={"action": "audit_ack", "notes": "trail complete"},
    )
    assert audit_ack.status_code == 200
    assert audit_ack.json()["workflow_state"] == "closed"
    patterns = client.get("/api/patterns", headers={"X-Analyst-Role": "analyst"})
    assert patterns.status_code == 200
    assert patterns.json()[0]["axes"]


def test_analyst_refer_is_fiu_only_except_showcase(isolated_db):
    from main import app
    from synthetic.showcase import HERO_TXN_ID, seed_showcase

    seed_showcase()
    _seed_case("T-REFER-1")
    client = TestClient(app)
    analyst = {"X-Analyst-Role": "analyst"}
    lead = {"X-Analyst-Role": "fiu_lead"}
    analyst_ids = {a["txn_id"] for a in client.get("/api/alerts", headers=analyst).json()}
    lead_ids = {a["txn_id"] for a in client.get("/api/alerts", headers=lead).json()}
    assert HERO_TXN_ID in analyst_ids
    assert HERO_TXN_ID in lead_ids
    assert "T-REFER-1" in analyst_ids
    assert "T-REFER-1" not in lead_ids
    sent = client.post(
        "/api/alerts/T-REFER-1/workflow",
        headers=analyst,
        json={"action": "refer_fiu", "notes": "needs FIU"},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["workflow_state"] == "referred_fiu"
    analyst_ids = {a["txn_id"] for a in client.get("/api/alerts", headers=analyst).json()}
    lead_ids = {a["txn_id"] for a in client.get("/api/alerts", headers=lead).json()}
    assert "T-REFER-1" not in analyst_ids
    assert "T-REFER-1" in lead_ids
    assert HERO_TXN_ID in analyst_ids
    assert HERO_TXN_ID in lead_ids


def test_investigate_survives_sparse_case(isolated_db):
    from main import app
    _seed_case("T-INV-1", sparse_risk=True)
    client = TestClient(app)
    res = client.post(
        "/api/alerts/T-INV-1/investigate",
        headers={"X-Analyst-Role": "analyst"},
        json={"mode": "deterministic", "force": True},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["verdict"]["mode"] == "deterministic"
    assert body["dag"]["trace"]


def test_notify_failure_does_not_break_ingest(isolated_db, monkeypatch):
    def boom(_payload):
        raise RuntimeError("pubsub down")

    monkeypatch.setattr("pubsub.publisher.notify_investigation", boom)
    result = ingest_transaction(
        _event(txn_id="T-NOTIFY-1", amount=15000, account_age_days=1),
        message_id="m-notify",
    )
    assert result["duplicate"] is False
    assert result["queued_for_investigation"] is True
    con = connect()
    row = con.execute("SELECT txn_id FROM investigation_queue WHERE txn_id='T-NOTIFY-1'").fetchone()
    con.close()
    assert row is not None


def test_ledger_stats_and_benchmark_persist(isolated_db, monkeypatch):
    import db as dbmod
    monkeypatch.setattr("db.DB_PATH", dbmod.DB_PATH)
    ingest_transaction(
        _event(txn_id="T-LEDGER-1", amount=15000, account_age_days=1),
        message_id="m-ledger",
    )
    from main import app
    client = TestClient(app)
    stats = client.get("/api/ledger-stats", headers={"X-Analyst-Role": "analyst"})
    assert stats.status_code == 200
    body = stats.json()
    assert body["ingestion_events"] >= 1
    assert body["investigation_queue"] >= 1
    assert "PostgreSQL investigation_queue" in body["investigation_path"]
    denied = client.post(
        "/api/benchmarks",
        headers={"X-Analyst-Role": "analyst"},
        json={"kind": "ingest", "payload": {"achieved_tps": 12.5, "mode": "in_process"}},
    )
    assert denied.status_code == 403
    saved = client.post(
        "/api/benchmarks",
        headers={"X-Analyst-Role": "fiu_lead"},
        json={"kind": "ingest", "payload": {"achieved_tps": 12.5, "mode": "in_process"}},
    )
    assert saved.status_code == 200
    card = client.get("/api/command-center?light=1", headers={"X-Analyst-Role": "analyst"})
    assert card.status_code == 200
    assert "PostgreSQL investigation_queue" in card.json()["investigation_path"]
    assert "ingest_stages_ms" in card.json()


def test_queue_survives_worker_kill(isolated_db):
    from investigations.queue import claim_next, mark_failed

    ingest_transaction(
        _event(txn_id="T-KILL-1", amount=15000, account_age_days=1),
        message_id="m-kill",
    )
    claimed = claim_next("worker-1", limit=1)
    assert claimed
    assert claimed[0]["status"] == "CLAIMED"
    status = mark_failed(claimed[0]["queue_id"], "worker killed", retry=True)
    assert status == "RETRY"
    again = claim_next("worker-2", limit=1)
    assert again
    assert again[0]["queue_id"] == claimed[0]["queue_id"]


def test_gcp_refuses_sqlite(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "gcp")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reset_settings_cache()
    with pytest.raises(RuntimeError, match="GCP requires DATABASE_URL"):
        connect()
    from main import health
    body = health()
    assert body["ok"] is False
    assert body["sqlite_forbidden_on_gcp"] is True
    monkeypatch.setenv("ENVIRONMENT", "local")
    reset_settings_cache()


def test_gemini_unavailable_ingest_still_works(isolated_db, monkeypatch):
    monkeypatch.setattr("agent.gemini_available", lambda: False)
    result = ingest_transaction(
        _event(txn_id="T-NOGEM", amount=15000, account_age_days=1),
        message_id="m-nogem",
    )
    assert result["gemini_invoked"] is False
    assert result["duplicate"] is False
    assert result["queued_for_investigation"] is True
    from investigations.service import process_queue_item
    processed = process_queue_item(txn_id="T-NOGEM")
    assert processed["txn_id"] == "T-NOGEM"
    assert processed["report"]["gemini_used"] is False


def test_transaction_baseline_metrics_exist(isolated_db):
    from evaluation import compare_to_transaction_baseline, impact_metrics, transaction_only_predict

    ingest_transaction(_event(txn_id="T-BASE-1", amount=9000, account_age_days=1, fraud_scenario="normal"), message_id="m-b1")
    ingest_transaction(_event(txn_id="T-BASE-2", amount=100, account_age_days=400, fraud_scenario="normal"), message_id="m-b2")
    assert transaction_only_predict({"amount": 9000, "account_age_days": 1}) is True
    assert transaction_only_predict({"amount": 100, "account_age_days": 400}) is False
    baseline = compare_to_transaction_baseline()
    assert baseline["name"] == "transaction_only"
    assert "precision" in baseline["metrics"]
    impact = impact_metrics({"metrics": {"recall": 0.9, "false_positive_rate": 0.1}}, baseline)
    assert "investigation_compression" in impact
    assert "false_positive_reduction" in impact
    assert "network_detection_lift" in impact
    assert "analyst_actionability_rate" in impact


def test_analyst_freeze_returns_fiu_message(isolated_db):
    ingest_transaction(
        _event(txn_id="T-FREEZE", amount=15000, account_age_days=1, fraud_scenario="mule_pass_through"),
        message_id="m-freeze",
    )
    from main import app
    client = TestClient(app)
    denied = client.post(
        "/api/alerts/T-FREEZE/decision",
        headers={"X-Analyst-Role": "analyst", "X-Analyst-ID": "a1"},
        json={"decision": "freeze_account", "notes": "try"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "FIU Lead authorization required"


def test_home_snapshot_queries_do_not_materialize_the_ledger(isolated_db):
    from graph.corridor import investigation_compression
    from graph.institutions import list_institutions

    ingest_transaction(_event(txn_id="T-HOME-1", amount=15000, account_age_days=1), message_id="m-home")
    comp = investigation_compression()
    assert comp["flagged_transactions"] >= 1
    assert comp["network_investigations"] >= 0
    rows = list_institutions()
    assert isinstance(rows, list)
    assert all("transaction_count" in r for r in rows)
