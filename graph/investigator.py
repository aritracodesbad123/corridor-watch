"""Bounded network investigation used by the investigation worker."""
from __future__ import annotations

from graph.builder import collect_bounded_txns
from graph.features import network_features


def bounded_network(txn: dict) -> dict:
    seeds = {txn.get("sender_id"), txn.get("receiver_id")} - {None, ""}
    txns = collect_bounded_txns(seeds, focus_ts=txn.get("ts"))
    nodes: dict[str, dict] = {}
    edges = []
    for t in txns:
        for nid, side in ((t["sender_id"], "sender"), (t["receiver_id"], "receiver")):
            nodes.setdefault(nid, {
                "id": nid,
                "kind": "account",
                "focus": nid in seeds,
            })
        edges.append({
            "source": t["sender_id"],
            "target": t["receiver_id"],
            "txn_id": t["txn_id"],
            "amount": t["amount"],
            "corridor": t.get("corridor"),
            "ts": t.get("ts"),
            "origin_bank_id": t.get("origin_bank_id"),
            "destination_bank_id": t.get("destination_bank_id"),
            "device_id": t.get("device_id"),
            "beneficiary_id": t.get("beneficiary_id"),
        })
    features = network_features(txns, seeds)
    return {
        "network_id": f"N-{txn.get('sender_id', '')[:8]}-{txn.get('receiver_id', '')[:8]}",
        "nodes": list(nodes.values()),
        "edges": edges,
        "features": features,
        "bounds": {
            "max_hops": True,
            "node_count": len(nodes),
            "edge_count": len(edges),
        },
    }
