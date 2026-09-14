import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from db import connect
from investigations.queue import claim_next, enqueue
from pubsub.ingestion import ingest_transaction
from validation.reliability.test_idempotency import _event

ROOT = Path(__file__).resolve().parents[2]


def test_concurrent_duplicate_ingest(isolated_db):
    ev = _event(txn_id="T-RACE", source_event_id="EVT-RACE")
    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(lambda i: ingest_transaction(ev, message_id=f"m-{i}"), range(10)))
    con = connect()
    n = con.execute("SELECT COUNT(*) AS c FROM transactions WHERE txn_id='T-RACE'").fetchone()["c"]
    q = con.execute("SELECT COUNT(*) AS c FROM investigation_queue WHERE txn_id='T-RACE'").fetchone()["c"]
    con.close()
    assert n == 1
    assert q == 1


def test_two_workers_one_claim(isolated_db):
    con = connect()
    enqueue(con, "Q-RACE", "T-CLAIM", "N-1", "HIGH")
    con.commit()
    con.close()

    def worker(wid):
        return [r["queue_id"] for r in claim_next(wid, limit=1)]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, ["w1", "w2"]))
    winners = [r for r in results if r]
    payload = {"failures": 0 if len(winners) == 1 else 1, "winners": winners}
    (ROOT / "reports" / "races.json").write_text(json.dumps(payload, indent=2))
    assert len(winners) == 1
