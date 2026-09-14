from graph.builder import collect_bounded_txns
from pubsub.ingestion import ingest_transaction
from validation.reliability.test_idempotency import _event


def test_star_and_deep_graphs_honor_caps(isolated_db):
    hub = "ACC-HUB"
    for i in range(30):
        ingest_transaction(
            _event(txn_id=f"T-STAR-{i}", source_event_id=f"E-STAR-{i}",
                   sender_account_id=hub, receiver_account_id=f"ACC-L{i}", amount=100 + i),
            message_id=f"m-star-{i}",
        )
    prev = "ACC-DEEP-0"
    for i in range(8):
        nxt = f"ACC-DEEP-{i+1}"
        ingest_transaction(
            _event(txn_id=f"T-DEEP-{i}", source_event_id=f"E-DEEP-{i}",
                   sender_account_id=prev, receiver_account_id=nxt, amount=200),
            message_id=f"m-deep-{i}",
        )
        prev = nxt
    star = collect_bounded_txns({hub}, max_hops=1, max_nodes=8, max_edges=8)
    assert len(star) <= 8
    deep = collect_bounded_txns({"ACC-DEEP-0"}, max_hops=2, max_nodes=200, max_edges=400)
    nodes = {t["sender_id"] for t in deep} | {t["receiver_id"] for t in deep}
    assert "ACC-DEEP-8" not in nodes


def test_window_includes_next_day_mule_payout(isolated_db):
    ingest_transaction(
        _event(txn_id="T-IN", source_event_id="E-IN", sender_account_id="FEED",
               receiver_account_id="MULE", amount=12000, timestamp="2026-01-01T00:00:00+00:00"),
        message_id="m-in",
    )
    ingest_transaction(
        _event(txn_id="T-OUT", source_event_id="E-OUT", sender_account_id="MULE",
               receiver_account_id="CASH", amount=11800, timestamp="2026-01-01T22:00:00+00:00"),
        message_id="m-out",
    )
    rows = collect_bounded_txns({"MULE"}, focus_ts="2026-01-01T00:00:00+00:00")
    ids = {r["txn_id"] for r in rows}
    assert "T-IN" in ids
    assert "T-OUT" in ids
