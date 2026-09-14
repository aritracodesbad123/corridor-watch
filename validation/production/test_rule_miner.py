import json
from pathlib import Path

from db import connect
from pubsub.ingestion import ingest_transaction
from rule_miner import mine_candidate_rules
from validation.reliability.test_idempotency import _event

ROOT = Path(__file__).resolve().parents[2]


def test_holdout_precision_is_measured_or_not_invented(isolated_db):
    empty = mine_candidate_rules()
    assert empty.get("holdout_precision") is None
    assert all(r.get("precision_percent") is None for r in empty["mined_rules"])
    for i in range(10):
        ingest_transaction(
            _event(txn_id=f"T-MINE-{i}", source_event_id=f"E-MINE-{i}", amount=15000, account_age_days=1),
            message_id=f"m-mine-{i}",
        )
        con = connect()
        con.execute(
            "INSERT INTO analyst_decisions (txn_id, decided_at, decision, notes, analyst_id) VALUES (?,?,?,?,?)",
            (f"T-MINE-{i}", "2026-01-01T00:00:00+00:00", "hold_payment" if i < 7 else "clear", "", "lead1"),
        )
        con.commit()
        con.close()
    mined = mine_candidate_rules(holdout=0.3)
    (ROOT / "reports" / "rule_miner_holdout.json").write_text(json.dumps(mined, indent=2, default=str))
    assert mined["train_n"] >= 1
    assert mined["holdout_n"] >= 1
    assert mined.get("label_source") == "analyst_disposition"
