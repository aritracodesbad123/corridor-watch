"""Sprint 3: traces, SLO snapshot, alert evaluation."""
from fastapi.testclient import TestClient

from metrics import MetricsRegistry


def test_health_echoes_trace_id():
    from main import app
    client = TestClient(app)
    res = client.get("/api/health", headers={"X-Trace-Id": "abc123traceid"})
    assert res.status_code == 200
    assert res.headers.get("X-Trace-Id") == "abc123traceid"


def test_traceparent_is_accepted():
    from tracing import start_request
    ctx = start_request({"traceparent": "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"})
    assert ctx["trace_id"] == "0123456789abcdef0123456789abcdef"
    assert ctx["span_id"]


def test_ingest_returns_trace_id(isolated_db):
    from pubsub.ingestion import ingest_transaction
    from pubsub.schemas import TransactionEvent
    from tracing import start_request

    start_request({"x-trace-id": "ingest-trace-1"})
    event = TransactionEvent.model_validate({
        "txn_id": "T-TR-1",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "sender_account_id": "A",
        "receiver_account_id": "B",
        "amount": 15000,
        "origin_country": "IN",
        "destination_country": "SG",
        "account_age_days": 1,
    })
    result = ingest_transaction(event, message_id="m-tr")
    assert result["trace_id"] == "ingest-trace-1"
    assert result["gemini_invoked"] is False


def test_slo_snapshot_includes_investigation_and_availability():
    snap = MetricsRegistry().snapshot()
    assert "investigation_within_10s" in snap["slos"]
    assert "api_availability" in snap["slos"]
    assert snap["slos"]["api_availability"]["note"]


def test_dlq_alert_fires_from_queue_counts():
    alerts = MetricsRegistry().evaluate_alerts(queue={"DEAD_LETTER": 2})
    ids = {a["id"] for a in alerts}
    assert "dlq" in ids


def test_pool_alert_fires_above_eighty_percent():
    alerts = MetricsRegistry().evaluate_alerts(pool={"utilization": 0.91})
    assert any(a["id"] == "db_pool" for a in alerts)


def test_metrics_endpoint_includes_alerts(isolated_db):
    from main import app
    client = TestClient(app)
    res = client.get("/api/metrics", headers={"X-Analyst-Role": "analyst"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert "slos" in body
    assert "alerts" in body
    assert "db_pool" in body
    assert "trace" in body
