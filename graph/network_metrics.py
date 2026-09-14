"""Network-level recall vs a hidden ground-truth graph."""
from __future__ import annotations


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
    return {
        "account_recall": _prf(p_nodes, t_nodes),
        "relationship_reconstruction": _prf(p_edges, t_edges),
        "key_node_recall": _prf(p_nodes & key_truth, key_truth) if key_truth else _prf(set(), set()),
        "path_recovery": _prf(p_edges, t_edges),
        "predicted_nodes": len(p_nodes),
        "truth_nodes": len(t_nodes),
    }
