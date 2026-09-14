from pubsub.ingestion import ingest_transaction
from investigations.service import process_queue_item
from validation.reliability.test_idempotency import _event


def test_pipeline_serves_when_gemini_off(isolated_db, monkeypatch):
    monkeypatch.setattr("agent.gemini_available", lambda: False)
    result = ingest_transaction(_event(txn_id="T-ISO", source_event_id="EVT-ISO"), message_id="m-iso")
    assert result["gemini_invoked"] is False
    processed = process_queue_item(txn_id="T-ISO")
    assert processed["report"]["gemini_used"] is False
