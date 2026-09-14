from fastapi.testclient import TestClient

from pubsub.ingestion import ingest_transaction
from validation.reliability.test_idempotency import _event


def test_expired_and_invalid_and_stale_recommendation(isolated_db):
    ingest_transaction(_event(txn_id="T-AUTHZ", source_event_id="EVT-AUTHZ"), message_id="m-authz")
    from main import app
    client = TestClient(app)
    missing = client.post(
        "/api/alerts/NO-SUCH/decision",
        headers={"X-Analyst-Role": "fiu_lead", "X-Analyst-ID": "lead1"},
        json={"decision": "hold_payment", "notes": "x"},
    )
    assert missing.status_code == 404
    stale = client.post(
        "/api/alerts/T-AUTHZ/decision",
        headers={"X-Analyst-Role": "fiu_lead", "X-Analyst-ID": "lead1"},
        json={"decision": "hold_payment", "notes": "x", "evidence_hash": "not-the-hash"},
    )
    assert stale.status_code == 409
    ok = client.post(
        "/api/alerts/T-AUTHZ/decision",
        headers={"X-Analyst-Role": "fiu_lead", "X-Analyst-ID": "lead1"},
        json={"decision": "hold_payment", "notes": "x"},
    )
    assert ok.status_code == 200
    conflict = client.post(
        "/api/alerts/T-AUTHZ/decision",
        headers={"X-Analyst-Role": "fiu_lead", "X-Analyst-ID": "lead1"},
        json={"decision": "clear", "notes": "flip"},
    )
    assert conflict.status_code == 200
