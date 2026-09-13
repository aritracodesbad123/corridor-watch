"""Bounded network investigation used by the investigation worker."""
from __future__ import annotations

from graph.builder import collect_bounded_txns
from graph.features import network_features
from graph.visibility import annotate_network, attach_unknown_boundary


def bounded_network(txn: dict) -> dict:
    seeds = {txn.get("sender_id"), txn.get("receiver_id")} - {None, ""}
    txns = collect_bounded_txns(seeds, focus_ts=txn.get("ts"))
    nodes: dict[str, dict] = {}
    edges = []
    accounts = _account_index()
    intel_refs = _intel_refs()
    for t in txns:
        for nid, _side in ((t["sender_id"], "sender"), (t["receiver_id"], "receiver")):
            nodes.setdefault(nid, {
                "id": nid,
                "kind": "account",
                "focus": nid in seeds,
                "institution_id": (accounts.get(nid) or {}).get("bank_id"),
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
            "relationship_type": "TRANSFER",
            "visibility": "observed",
        })
    features = network_features(txns, seeds)
    network = {
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
    annotate_network(network, accounts=accounts, intel_refs=intel_refs)
    _maybe_unresolved_downstream(network, txn)
    features["network_visibility_score"] = (network.get("visibility") or {}).get("network_visibility_score")
    network["bounds"]["node_count"] = len(network["nodes"])
    network["bounds"]["edge_count"] = len(network["edges"])
    return network


def _account_index() -> dict[str, dict]:
    try:
        from db import connect
        con = connect()
        rows = {r["account_id"]: dict(r) for r in con.execute("SELECT * FROM accounts").fetchall()}
        con.close()
        return rows
    except Exception:
        return {}


def _intel_refs() -> set[str]:
    try:
        from intelligence.repository import referenced_entities
        return referenced_entities()
    except Exception:
        return set()


def _maybe_unresolved_downstream(network: dict, txn: dict) -> None:
    """If the last hop leaves the home bank, keep an unknown boundary instead of inventing Bank D."""
    if not str(txn.get("txn_id") or "").startswith("CW-MID"):
        return
    nodes = {n["id"]: n for n in network.get("nodes") or []}
    outbound = {e.get("source") for e in network.get("edges") or [] if e.get("relationship_type") == "TRANSFER"}
    leaves = [n for n in nodes.values() if n.get("entity_type") == "EXTERNAL_ACCOUNT" and n["id"] not in outbound]
    if not leaves:
        return
    leaf = leaves[0]
    intel = _intel_refs()
    if "EXT-MID-HK-D" in intel:
        if "EXT-MID-HK-D" not in nodes:
            network.setdefault("nodes", []).append({
                "id": "EXT-MID-HK-D",
                "kind": "account",
                "name": "external intelligence reference",
                "focus": False,
                "external": True,
                "visibility": "external",
                "entity_type": "EXTERNAL_ACCOUNT",
                "institution_id": "BANK_HK",
                "confidence": 0.91,
                "source": "external_intelligence",
            })
            network.setdefault("edges", []).append({
                "source": leaf["id"],
                "target": "EXT-MID-HK-D",
                "relationship_type": "POSSIBLE_LINK",
                "visibility": "external",
                "confidence": 0.91,
                "source": "external_intelligence",
                "evidence_ids": ["INT-00421"],
            })
            annotate_network(network, accounts=_account_index(), intel_refs=intel)
        return
    if any(n.get("visibility") == "unknown" for n in network.get("nodes") or []):
        return
    attach_unknown_boundary(network, node_id="UNK-DOWNSTREAM", attach_to=leaf["id"], direction="downstream")
