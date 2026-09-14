import json
from pathlib import Path

from db import connect
from graph_features import score_all, write_scores
from rule_miner import mine_candidate_rules
from validation.external.generator_b import write_db
from validation.external.hard_negatives import POSITIVE, build
from validation.oracle import extract, is_positive

ROOT = Path(__file__).resolve().parents[2]


def test_holdout_precision_is_measured_or_not_invented(isolated_db):
    empty = mine_candidate_rules()
    assert empty.get("holdout_precision") is None
    assert all(r.get("precision_percent") is None for r in empty["mined_rules"])
    accounts, txns, _roles = build()
    write_db(accounts, txns)
    con = connect()
    scores, scored_txns, _ = score_all(con)
    write_scores(con, scores, scored_txns)
    labels = extract(scored_txns, POSITIVE)
    for t in scored_txns:
        decision = "hold_payment" if is_positive(t["txn_id"], labels) else "clear"
        con.execute(
            "INSERT INTO analyst_decisions (txn_id, decided_at, decision, notes, analyst_id) VALUES (?,?,?,?,?)",
            (t["txn_id"], t.get("ts") or "2026-01-01T00:00:00+00:00", decision, "", "lead1"),
        )
    con.commit()
    con.close()
    mined = mine_candidate_rules(holdout=0.3)
    (ROOT / "reports" / "rule_miner_holdout.json").write_text(json.dumps(mined, indent=2, default=str))
    assert mined["train_n"] >= 1
    assert mined["holdout_n"] >= 1
    assert mined.get("label_source") == "analyst_disposition"
    assert mined.get("holdout_precision") is not None
