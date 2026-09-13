"""Sprint 1 reliability: source-event identity, outbox, backoff."""
from datetime import datetime, timezone

from metrics import METRICS
from pubsub.ingestion import ingest_transaction
from pubsub.schemas import TransactionEvent


def _event(**kwargs) -> TransactionEvent:
    body = {
        "txn_id": "T-REL-1",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "sender_account_id": "ACC-A",
        "receiver_account_id": "ACC-B",
        "amount": 15000,
        "origin_country": "IN",
        "destination_country": "SG",
        "account_age_days": 1,
        "fraud_scenario": "mule_pass_through",
    }
    body.update(kwargs)
    return TransactionEvent.model_validate(body)


def test_source_event_id_is_duplicate_across_message_ids(isolated_db):
    event = _event(txn_id="T-SRC-1", source_system="bank-sg", source_event_id="EVT-99")
    first = ingest_transaction(event, message_id="m-a")
    second = ingest_transaction(event, message_id="m-b")
    assert first["duplicate"] is False
    assert first["gemini_invoked"] is False
    assert first["source_event_id"] == "EVT-99"
    assert second["duplicate"] is True
    from db import connect
    con = connect()
    n = con.execute("SELECT COUNT(*) AS c FROM transactions WHERE txn_id='T-SRC-1'").fetchone()["c"]
    q = con.execute("SELECT COUNT(*) AS c FROM investigation_queue WHERE txn_id='T-SRC-1'").fetchone()["c"]
    con.close()
    assert n == 1
    assert q == 1


def test_outbox_row_commits_with_queue(isolated_db):
    result = ingest_transaction(_event(txn_id="T-OB-1"), message_id="m-ob")
    assert result["queued_for_investigation"] is True
    from db import connect
    con = connect()
    row = con.execute(
        "SELECT event_type, payload, published_at FROM outbox_events WHERE payload LIKE '%T-OB-1%'"
    ).fetchone()
    queued = con.execute("SELECT txn_id FROM investigation_queue WHERE txn_id='T-OB-1'").fetchone()
    con.close()
    assert queued is not None
    assert row is not None
    assert row["event_type"] == "investigation_queued"
    assert "T-OB-1" in row["payload"]


def test_retry_records_backoff(isolated_db):
    from investigations.queue import claim_next, mark_failed

    ingest_transaction(_event(txn_id="T-BK-1"), message_id="m-bk")
    claimed = claim_next("w1", limit=1)
    assert claimed
    status = mark_failed(claimed[0]["queue_id"], "boom", retry=True)
    assert status == "RETRY"
    from db import connect
    con = connect()
    row = con.execute(
        "SELECT attempt_count, status, next_attempt_at, last_error FROM investigation_queue WHERE txn_id='T-BK-1'"
    ).fetchone()
    con.close()
    assert row["status"] == "RETRY"
    assert row["last_error"] == "boom"
    assert row["next_attempt_at"]


def test_dead_letter_after_max_attempts(isolated_db):
    from investigations.queue import MAX_ATTEMPTS, claim_next, mark_failed

    ingest_transaction(_event(txn_id="T-DLQ-1"), message_id="m-dlq")
    claimed = claim_next("w-dlq", limit=1)
    assert claimed
    from db import connect
    con = connect()
    con.execute(
        "UPDATE investigation_queue SET attempt_count=? WHERE queue_id=?",
        (MAX_ATTEMPTS, claimed[0]["queue_id"]),
    )
    con.commit()
    con.close()
    assert mark_failed(claimed[0]["queue_id"], "exhausted", retry=True) == "DEAD_LETTER"


def test_metrics_snapshot_includes_measured_slos():
    snap = METRICS.snapshot()
    assert "slos" in snap
    assert "ingestion_accept_within_2s" in snap["slos"]
    assert "target" in snap["slos"]["ingestion_accept_within_2s"]
    assert snap["slos"]["ingestion_accept_within_2s"]["p95_ms"] is not None


def test_grounded_prompt_treats_documents_as_untrusted():
    from agent import GROUNDED_SYSTEM_PROMPT
    assert "untrusted" in GROUNDED_SYSTEM_PROMPT.lower()
    assert "document_verification" in GROUNDED_SYSTEM_PROMPT


def test_deterministic_report_records_prompt_version(isolated_db):
    from investigations.service import process_queue_item

    ingest_transaction(_event(txn_id="T-HASH-1"), message_id="m-hash")
    processed = process_queue_item(txn_id="T-HASH-1")
    report = processed["report"]
    assert report["prompt_version"] == "investigator-v8"
    assert report["evidence_hash"]
    assert report["gemini_used"] is False
    assert processed.get("status") != "empty"


def test_case_phase_is_human_review_after_queue(isolated_db):
    from db import connect
    from investigations.service import process_queue_item

    ingest_transaction(_event(txn_id="T-PHASE-1"), message_id="m-phase")
    process_queue_item(txn_id="T-PHASE-1")
    con = connect()
    row = con.execute("SELECT status FROM investigations WHERE case_id='T-PHASE-1'").fetchone()
    con.close()
    assert row["status"] == "HUMAN_REVIEW"


def test_fifth_retry_uses_later_backoff_window(isolated_db):
    from investigations.queue import BACKOFF_SECONDS, claim_next, mark_failed

    ingest_transaction(_event(txn_id="T-DLY-1"), message_id="m-dly")
    first = claim_next("w-delay", limit=1)
    mark_failed(first[0]["queue_id"], "first", retry=True)
    second = claim_next("w-delay-2", limit=1)
    assert second
    mark_failed(second[0]["queue_id"], "second", retry=True)
    from db import connect
    con = connect()
    row = con.execute(
        "SELECT next_attempt_at, attempt_count FROM investigation_queue WHERE txn_id='T-DLY-1'"
    ).fetchone()
    con.close()
    nxt = datetime.fromisoformat(row["next_attempt_at"])
    now = datetime.now(timezone.utc)
    assert row["attempt_count"] == 2
    assert (nxt - now).total_seconds() > (BACKOFF_SECONDS[1] - 0.75)
