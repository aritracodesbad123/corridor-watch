from fastapi.testclient import TestClient

from pubsub.ingestion import ingest_transaction
from validation.reliability.test_idempotency import _event


def test_queue_investigate_decision_audit_export(isolated_db):
    ingest_transaction(_event(txn_id="T-UX", source_event_id="EVT-UX"), message_id="m-ux")
    from main import app
    client = TestClient(app)
    headers = {"X-Analyst-Role": "fiu_lead", "X-Analyst-ID": "lead"}
    alerts = client.get("/api/alerts", headers=headers)
    assert alerts.status_code == 200
    inv = client.post(
        "/api/alerts/T-UX/investigate",
        headers={**headers, "X-Analyst-Role": "analyst"},
        json={"mode": "deterministic", "force": True},
    )
    assert inv.status_code == 200
    body = inv.json()
    assert body.get("verdict") or body.get("investigation_report") or body.get("dag")
    dec = client.post("/api/alerts/T-UX/decision", headers=headers, json={"decision": "monitor", "notes": "ux"})
    assert dec.status_code == 200
    audit = client.get("/api/alerts/T-UX/audit", headers=headers)
    assert audit.status_code == 200
    assert audit.json()
    exported = client.get("/api/alerts/T-UX/export", headers=headers)
    assert exported.status_code == 200
    sar = client.get("/api/alerts/T-UX/sar?jurisdiction=fincen", headers=headers)
    assert sar.status_code == 200
    cf = client.post(
        "/api/alerts/T-UX/counterfactual",
        headers=headers,
        json={"account_age_days": 400},
    )
    assert cf.status_code == 200
