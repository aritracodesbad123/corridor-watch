import json
from pathlib import Path

from graph_features import FLAG_THRESHOLD, score_all
from validation import stamped
from validation.external.generator_b import write_db
from validation.external.hard_negatives import POSITIVE, build
from validation.oracle import extract, is_positive, label_of

ROOT = Path(__file__).resolve().parents[2]


def test_hard_negative_networks_vs_fraud_twins(tmp_path, monkeypatch):
    import db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "hn.db")
    accounts, txns, roles = build()
    write_db(accounts, txns)
    con = db.connect()
    scores, _, _ = score_all(con)
    con.close()
    labels = extract(txns, POSITIVE)
    y_true, y_pred, legit_scores, fraud_scores = [], [], [], []
    by_kind = {}
    for t in txns:
        risk = max(
            float((scores.get(t["sender_id"]) or {}).get("risk_score") or 0),
            float((scores.get(t["receiver_id"]) or {}).get("risk_score") or 0),
        )
        truth = is_positive(t["txn_id"], labels)
        pred = risk >= FLAG_THRESHOLD
        y_true.append(truth)
        y_pred.append(pred)
        kind = label_of(t["txn_id"], labels)
        by_kind.setdefault(kind, {"n": 0, "flagged": 0})
        by_kind[kind]["n"] += 1
        by_kind[kind]["flagged"] += int(pred)
        (fraud_scores if truth else legit_scores).append(risk)
    tp = sum(a and b for a, b in zip(y_true, y_pred))
    fp = sum((not a) and b for a, b in zip(y_true, y_pred))
    fn = sum(a and (not b) for a, b in zip(y_true, y_pred))
    tn = sum((not a) and (not b) for a, b in zip(y_true, y_pred))
    fpr = fp / (fp + tn) if fp + tn else 0.0
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    payload = {
        "n": len(txns),
        "archetypes": sorted({(roles[a]["typology"]) for a in roles}),
        "frozen_seed": 19,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "fpr": round(fpr, 4),
        "hard_negative_fpr": round(fpr, 4),
        "legit_mean_score": round(sum(legit_scores) / len(legit_scores), 2) if legit_scores else None,
        "fraud_mean_score": round(sum(fraud_scores) / len(fraud_scores), 2) if fraud_scores else None,
        "by_label": by_kind,
        "note": "Networks, not single wires. Runtime ignores fraud_scenario.",
    }
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "hard_negative_results.json").write_text(json.dumps(stamped(payload, dataset="hard_negatives", random_seed=19), indent=2))
    (reports / "hard_negative_report.md").write_text(
        f"# Hard-negative network benchmark\n\n"
        f"n={payload['n']} archetypes={payload['archetypes']}\n\n"
        f"FPR={payload['fpr']} precision={payload['precision']} recall={payload['recall']}\n"
        f"legit mean score={payload['legit_mean_score']} fraud mean={payload['fraud_mean_score']}\n\n"
        f"Feature note: legitimate archetypes are source-only or old-account disbursement "
        f"(payroll/treasury/marketplace/etc.). Fraud twins reuse the same skeleton with inbound "
        f"fan-in or pass-through. Runtime ignores `fraud_scenario`.\n"
    )
    (reports / "hard_negatives.json").write_text(json.dumps({
        "n": payload["n"],
        "kinds": payload["archetypes"],
        "screen_fpr": payload["fpr"],
        "fpr": payload["fpr"],
        "dag_fp": fp,
    }, indent=2))
    assert len(payload["archetypes"]) >= 10
    assert payload["recall"] >= 0.7
    assert fpr <= 0.10
