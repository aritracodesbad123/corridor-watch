from fastapi import HTTPException
from fastapi.testclient import TestClient

from pubsub.ingestion import ingest_transaction
from validation.reliability.test_idempotency import _event


def test_analyst_cannot_freeze(isolated_db):
    ingest_transaction(_event(txn_id="T-RBAC", source_event_id="EVT-RBAC"), message_id="m-rbac")
    from main import app
    client = TestClient(app)
    denied = client.post(
        "/api/alerts/T-RBAC/decision",
        headers={"X-Analyst-Role": "analyst", "X-Analyst-ID": "a1"},
        json={"decision": "freeze_account", "notes": "no"},
    )
    assert denied.status_code == 403


def test_header_spoof_disabled_on_gcp(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "gcp")
    from auth import get_auth_context
    from config import reset_settings_cache
    reset_settings_cache()
    try:
        get_auth_context(None, "spoof", "fiu_lead", None, None)
        raised = False
    except HTTPException:
        raised = True
    reset_settings_cache()
    assert raised
