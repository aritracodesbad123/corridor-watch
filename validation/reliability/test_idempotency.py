from pubsub.ingestion import ingest_transaction
from pubsub.schemas import TransactionEvent
from db import connect


def _event(**kwargs):
    body = {
        "txn_id": "T-VAL-1",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "sender_account_id": "A",
        "receiver_account_id": "B",
        "amount": 15000,
        "origin_country": "IN",
        "destination_country": "SG",
        "account_age_days": 1,
        "source_system": "bank-sg",
        "source_event_id": "EVT-VAL",
    }
    body.update(kwargs)
    return TransactionEvent.model_validate(body)


def test_duplicate_source_event_single_ledger_row(isolated_db):
    ev = _event()
    ingest_transaction(ev, message_id="m1")
    ingest_transaction(ev, message_id="m2")
    con = connect()
    n = con.execute("SELECT COUNT(*) AS c FROM transactions WHERE txn_id='T-VAL-1'").fetchone()["c"]
    q = con.execute("SELECT COUNT(*) AS c FROM investigation_queue WHERE txn_id='T-VAL-1'").fetchone()["c"]
    con.close()
    assert n == 1
    assert q == 1
