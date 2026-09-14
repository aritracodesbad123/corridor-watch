from pubsub.ingestion import ingest_transaction
from validation.reliability.test_idempotency import _event
from db import connect


def test_outbox_commits_with_queue(isolated_db):
    ingest_transaction(_event(txn_id="T-OB-V", source_event_id="EVT-OB"), message_id="m-ob")
    con = connect()
    row = con.execute("SELECT payload FROM outbox_events WHERE payload LIKE '%T-OB-V%'").fetchone()
    queued = con.execute("SELECT txn_id FROM investigation_queue WHERE txn_id='T-OB-V'").fetchone()
    con.close()
    assert queued is not None
    assert row is not None
