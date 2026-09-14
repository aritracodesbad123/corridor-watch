from investigations.queue import BACKOFF_SECONDS, MAX_ATTEMPTS, claim_next, mark_failed
from pubsub.ingestion import ingest_transaction
from validation.reliability.test_idempotency import _event


def test_backoff_then_dead_letter(isolated_db):
    ingest_transaction(_event(txn_id="T-DLQ-V", source_event_id="EVT-DLQ"), message_id="m-d")
    claimed = claim_next("w", limit=1)
    from db import connect
    con = connect()
    con.execute("UPDATE investigation_queue SET attempt_count=? WHERE queue_id=?", (MAX_ATTEMPTS, claimed[0]["queue_id"]))
    con.commit()
    con.close()
    assert mark_failed(claimed[0]["queue_id"], "exhausted", retry=True) == "DEAD_LETTER"
    assert MAX_ATTEMPTS <= 5
    assert BACKOFF_SECONDS[-1] >= 30
