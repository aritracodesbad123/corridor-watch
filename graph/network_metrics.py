"""Network-level recall vs a hidden ground-truth graph."""
from __future__ import annotations

from collections import Counter, defaultdict


NA = "not_applicable"


def _prf(pred: set, truth: set) -> dict:
    tp = len(pred & truth)
    fp = len(pred - truth)
    fn = len(truth - pred)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn}


def score_network(predicted: dict, truth: dict) -> dict:
    p_nodes = {n.get("id") for n in predicted.get("nodes") or [] if n.get("id")}
    t_nodes = set(truth.get("nodes") or [])
    p_edges = {(e.get("source"), e.get("target")) for e in predicted.get("edges") or []}
    t_edges = {tuple(e) if isinstance(e, (list, tuple)) else (e.get("source"), e.get("target")) for e in (truth.get("edges") or [])}
    key_truth = set(truth.get("key_nodes") or [])
    ranked_ids = [
        n.get("id") for n in sorted(
            predicted.get("nodes") or [],
            key=lambda n: (not bool(n.get("focus")), -float(n.get("risk_score") or 0)),
        )
        if n.get("id")
    ]
    anchors = set(truth.get("anchors") or [])
    critical = set(truth.get("critical_nodes") or anchors)
    c_edges = {
        tuple(e) if isinstance(e, (list, tuple)) else (e.get("source"), e.get("target"))
        for e in (truth.get("critical_edges") or [])
    }
    path = [p for p in (truth.get("path") or []) if p]
    path_edges = set(zip(path, path[1:]))

    def _recall_at(k: int):
        if not critical:
            return NA
        return round(len(set(ranked_ids[:k]) & critical) / len(critical), 4)

    path_ok = NA if not path_edges else (1.0 if path_edges <= p_edges else 0.0)

    return {
        "account_recall": _prf(p_nodes, t_nodes),
        "relationship_reconstruction": _prf(p_edges, t_edges),
        "key_node_recall": _prf(p_nodes & key_truth, key_truth) if key_truth else NA,
        "path_recovery": _prf(p_edges, t_edges),
        "anchor_recall": _prf(p_nodes & anchors, anchors) if anchors else NA,
        "critical_node_recall": _prf(p_nodes & critical, critical) if critical else NA,
        "critical_edge_recall": _prf(p_edges & c_edges, c_edges) if c_edges else NA,
        "investigation_path_recovery": path_ok,
        "recall_at_10": _recall_at(10),
        "recall_at_20": _recall_at(20),
        "recall_at_50": _recall_at(50),
        "predicted_nodes": len(p_nodes),
        "truth_nodes": len(t_nodes),
    }


def partition_components(txns: list[dict]) -> list[list[dict]]:
    """One investigation = one connected component, not every mule in the ledger."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for t in txns:
        union(t["sender_id"], t["receiver_id"])
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in txns:
        groups[find(t["sender_id"])].append(t)
    return list(groups.values())


def hub_seed(cluster: list[dict]) -> dict:
    counts: Counter[str] = Counter()
    for t in cluster:
        counts[t["sender_id"]] += 1
        counts[t["receiver_id"]] += 1
    hub = counts.most_common(1)[0][0]
    return next(t for t in cluster if t["sender_id"] == hub or t["receiver_id"] == hub)
