"""Dev probe: generator C topologies on seed 31. Not frozen C. Not a SCORECARD gate."""
from __future__ import annotations

import json

from graph_features import FLAG_THRESHOLD, score_all
from validation import ROOT, stamped
from validation.external.generator_b import write_db
from validation.external.generator_c import POSITIVE_C, build
from validation.oracle import extract, is_positive, label_of

REPORTS = ROOT / "reports"


def test_probe_seed_31_records_without_gating(tmp_path, monkeypatch):
    import db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "probe31.db")
    accounts, txns = build(seed=31)
    write_db(accounts, txns)
    con = db.connect()
    scores, _, _ = score_all(con)
    con.close()
    labels = extract(txns, POSITIVE_C)
    y_true, y_pred = [], []
    by = {}
    for t in txns:
        risk = max(
            float((scores.get(t["sender_id"]) or {}).get("risk_score") or 0),
            float((scores.get(t["receiver_id"]) or {}).get("risk_score") or 0),
        )
        truth = is_positive(t["txn_id"], labels)
        pred = risk >= FLAG_THRESHOLD
        y_true.append(truth)
        y_pred.append(pred)
        lab = label_of(t["txn_id"], labels)
        by.setdefault(lab, {"n": 0, "flagged": 0})
        by[lab]["n"] += 1
        by[lab]["flagged"] += int(pred)
    tp = sum(a and b for a, b in zip(y_true, y_pred))
    fp = sum((not a) and b for a, b in zip(y_true, y_pred))
    fn = sum(a and (not b) for a, b in zip(y_true, y_pred))
    tn = sum((not a) and (not b) for a, b in zip(y_true, y_pred))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    payload = stamped({
        "probe_seed": 31,
        "note": "C-like topologies, not frozen seed 23. Not a SCORECARD gate.",
        "n": len(txns),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0,
        "false_positive_rate": round(fpr, 4),
        "by_label": by,
    }, dataset="dist_c_probe31", random_seed=31)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "dist_c_probe31.json").write_text(json.dumps(payload, indent=2))
    assert payload["n"] >= 80
