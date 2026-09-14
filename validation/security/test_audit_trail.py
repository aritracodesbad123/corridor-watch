import json

import audit
from pubsub.ingestion import ingest_transaction
from validation.reliability.test_idempotency import _event
from fastapi.testclient import TestClient


def test_workflow_writes_authorization_event(isolated_db):
    ingest_transaction(_event(txn_id="T-AUD", source_event_id="EVT-AUD"), message_id="m-aud")
    from main import app
    client = TestClient(app)
    res = client.post(
        "/api/alerts/T-AUD/workflow",
        headers={"X-Analyst-Role": "analyst", "X-Analyst-ID": "a1"},
        json={"action": "start_review", "notes": "open"},
    )
    assert res.status_code == 200
    events = audit.list_for_case("T-AUD")
    kinds = {e["event_type"] for e in events}
    assert "authorization" in kinds
    detail = json.loads([e for e in events if e["event_type"] == "authorization"][-1]["detail"])
    assert detail["who"] == "a1"
