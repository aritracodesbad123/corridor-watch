import json
from collections import defaultdict
from pathlib import Path

from graph.investigator import bounded_network
from graph.network_metrics import hub_seed, partition_components, score_network
from graph_features import score_all, write_scores
from validation.external.generator_b import POSITIVE_B, SEED, build as build_b, write_db
from validation.external.hard_negatives import POSITIVE as HN_POS
from validation.external.hard_negatives import build as build_hn
from validation.oracle import extract, is_positive, label_of

ROOT = Path(__file__).resolve().parents[2]


def _mean(rows, key):
    vals = []
    for r in rows:
        v = r.get(key)
        if isinstance(v, dict):
            v = v.get("recall")
        if v is not None:
            vals.append(float(v))
    return round(sum(vals) / len(vals), 4) if vals else None


def test_investigation_useful_network_metrics(tmp_path, monkeypatch):
    import db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "netv2.db")
    acc_b, tx_b = build_b(seed=SEED)
    acc_h, tx_h, roles = build_hn()
    # disjoint ids already (HUB vs PAYROLL prefixes)
    write_db(acc_b + acc_h, tx_b + tx_h)
    con = db.connect()
    scores, txns, _ = score_all(con)
    write_scores(con, scores, txns)
    con.close()

    labels = extract(txns, POSITIVE_B | HN_POS)
    clusters = defaultdict(list)
    for t in txns:
        if is_positive(t["txn_id"], labels):
            clusters[label_of(t["txn_id"], labels)].append(t)

    per = []
    for lab, cluster in clusters.items():
        for component in partition_components(cluster):
            truth_nodes = {t["sender_id"] for t in component} | {t["receiver_id"] for t in component}
            truth_edges = [(t["sender_id"], t["receiver_id"]) for t in component]
            anchors, critical, path = set(), set(), []
            for nid in truth_nodes:
                meta = roles.get(nid) or {}
                if meta.get("role") == "anchor" or nid.startswith(("HUB", "SMURF", "MULE")):
                    anchors.add(nid)
                    critical.add(nid)
                if meta.get("critical") or meta.get("role") in {"anchor", "critical"}:
                    critical.add(nid)
                if meta.get("path") and set(meta["path"]) <= truth_nodes:
                    path = meta["path"]
            if not anchors:
                anchors = {n for n in truth_nodes if n.startswith(("HUB-", "SMURF-", "R-000"))}
                critical = set(anchors) | {n for n in truth_nodes if n.startswith(("IN-", "R-"))}
            seed = hub_seed(component)
            pred = bounded_network({**seed, **(scores.get(seed["sender_id"]) or {})})
            for node in pred.get("nodes") or []:
                node["risk_score"] = float((scores.get(node.get("id")) or {}).get("risk_score") or 0)
            scored = score_network(pred, {
                "nodes": truth_nodes,
                "edges": truth_edges,
                "key_nodes": critical or truth_nodes,
                "anchors": anchors,
                "critical_nodes": critical or anchors,
                "critical_edges": truth_edges,
                "path": path or [seed["sender_id"], seed["receiver_id"]],
            })
            per.append({"label": lab, "visibility": "observed", **scored})

    payload = {
        "clusters": len(per),
        "account_recall": _mean(per, "account_recall"),
        "key_node_recall": _mean(per, "key_node_recall"),
        "relationship_reconstruction": _mean(per, "relationship_reconstruction"),
        "path_recovery": _mean(per, "path_recovery"),
        "anchor_recall": _mean(per, "anchor_recall"),
        "critical_node_recall": _mean(per, "critical_node_recall"),
        "critical_edge_recall": _mean(per, "critical_edge_recall"),
        "investigation_path_recovery": _mean(per, "investigation_path_recovery"),
        "recall_at_10": _mean(per, "recall_at_10"),
        "recall_at_20": _mean(per, "recall_at_20"),
        "recall_at_50": _mean(per, "recall_at_50"),
        "per_typology": per,
        "note": "Existing full-graph account recall kept in reports/network_metrics.json. These rows are investigation-useful.",
    }
    reports = ROOT / "reports"
    (reports / "network_evaluation_v2.json").write_text(json.dumps(payload, indent=2, default=str))
    (reports / "network_evaluation_v2.md").write_text(
        f"# Network evaluation v2\n\n"
        f"anchor={payload['anchor_recall']} critical_node={payload['critical_node_recall']} "
        f"critical_edge={payload['critical_edge_recall']} path={payload['investigation_path_recovery']} "
        f"r@10={payload['recall_at_10']}\n\n"
        f"Full-graph account recall remains in `reports/network_metrics.json`.\n"
    )
    assert payload["clusters"] >= 1
    assert payload["anchor_recall"] is not None
