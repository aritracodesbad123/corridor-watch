from investigations.queue import claim_next, mark_failed
from pubsub.ingestion import ingest_transaction
from validation.reliability.test_idempotency import _event


def test_killed_worker_does_not_lose_alert(isolated_db):
    ingest_transaction(_event(txn_id="T-KILL-V", source_event_id="EVT-KILL"), message_id="m-k")
    first = claim_next("w1", limit=1)
    assert first
    mark_failed(first[0]["queue_id"], "killed", retry=True)
    again = claim_next("w2", limit=1)
    assert again
    assert again[0]["queue_id"] == first[0]["queue_id"]
