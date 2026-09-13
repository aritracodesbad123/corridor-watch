"""Observed / external / inferred / unknown network visibility.

Visibility is not guilt. Risk stays on its own axis.
"""
from __future__ import annotations

import os
from collections import Counter

OBSERVED = "observed"
EXTERNAL = "external"
INFERRED = "inferred"
UNKNOWN = "unknown"


def home_institution() -> str:
    return os.getenv("CW_HOME_BANK", "BANK_SG")


def classify_account(account_id: str, accounts: dict[str, dict] | None = None, intel_refs: set[str] | None = None) -> dict:
    """Provenance for one account node. Does not invent missing counterparties."""
    aid = str(account_id or "")
    acc = (accounts or {}).get(aid) or {}
    intel = intel_refs or set()
    home = home_institution()
    bank_id = acc.get("bank_id") or ""
    if aid in intel:
        return {
            "visibility": EXTERNAL,
            "entity_type": "EXTERNAL_ACCOUNT",
            "institution_id": bank_id or None,
            "institution_subtype": "EXTERNAL_INSTITUTION",
            "confidence": 0.85,
            "source": "external_intelligence",
        }
    if aid.startswith("UNK-") or aid.startswith("UNKNOWN"):
        return {
            "visibility": UNKNOWN,
            "entity_type": "UNKNOWN_ACCOUNT",
            "institution_id": None,
            "institution_subtype": None,
            "confidence": 0.2,
            "source": "unresolved_boundary",
        }
    if acc and bank_id == home:
        return {
            "visibility": OBSERVED,
            "entity_type": "INTERNAL_ACCOUNT",
            "institution_id": bank_id,
            "institution_subtype": "INTERNAL_INSTITUTION",
            "confidence": 1.0,
            "source": "ledger",
        }
    if acc or aid.startswith("EXT"):
        return {
            "visibility": OBSERVED,
            "entity_type": "EXTERNAL_ACCOUNT",
            "institution_id": bank_id or None,
            "institution_subtype": "EXTERNAL_INSTITUTION" if bank_id else None,
            "confidence": 0.9 if acc else 0.7,
            "source": "ledger_counterparty",
        }
    return {
        "visibility": OBSERVED,
        "entity_type": "EXTERNAL_ACCOUNT",
        "institution_id": None,
        "institution_subtype": None,
        "confidence": 0.7,
        "source": "ledger_counterparty",
    }


def visibility_score(nodes: list[dict], edges: list[dict], boundaries: list[dict] | None = None) -> dict:
    """0–1 coverage indicator. Not a probability of guilt."""
    n_vis = Counter(str(n.get("visibility") or OBSERVED) for n in nodes)
    e_vis = Counter(str(e.get("visibility") or OBSERVED) for e in edges)
    unknown_n = n_vis.get(UNKNOWN, 0) + len(boundaries or [])
    inferred_e = e_vis.get(INFERRED, 0)
    observed_n = n_vis.get(OBSERVED, 0)
    observed_e = e_vis.get(OBSERVED, 0)
    total_n = max(1, len(nodes) + unknown_n)
    total_e = max(1, len(edges) + inferred_e)
    coverage = (
        0.45 * (observed_n / total_n)
        + 0.25 * (observed_e / total_e)
        + 0.15 * (n_vis.get(EXTERNAL, 0) / total_n)
        + 0.15 * (1.0 - min(1.0, unknown_n / total_n))
    )
    score = round(max(0.0, min(1.0, coverage)), 3)
    return {
        "network_visibility_score": score,
        "network_visibility_pct": int(round(score * 100)),
        "label": "visibility_indicator",
        "note": "Coverage of the visible network, not confidence of guilt.",
        "observed": {"nodes": n_vis.get(OBSERVED, 0), "edges": e_vis.get(OBSERVED, 0)},
        "external": {"nodes": n_vis.get(EXTERNAL, 0), "edges": e_vis.get(EXTERNAL, 0)},
        "inferred": {"nodes": n_vis.get(INFERRED, 0), "edges": e_vis.get(INFERRED, 0)},
        "unknown": {"nodes": n_vis.get(UNKNOWN, 0), "boundaries": len(boundaries or [])},
    }


def annotate_network(network: dict, *, accounts: dict[str, dict] | None = None, intel_refs: set[str] | None = None) -> dict:
    """Add visibility fields in place. Keeps existing node/edge keys."""
    accounts = accounts or {}
    intel_refs = intel_refs or set()
    nodes = list(network.get("nodes") or [])
    edges = list(network.get("edges") or [])
    for node in nodes:
        meta = classify_account(node.get("id") or "", accounts, intel_refs)
        node.setdefault("visibility", meta["visibility"])
        node.setdefault("entity_type", meta["entity_type"])
        node.setdefault("institution_id", meta["institution_id"] or node.get("institution_id"))
        node.setdefault("institution_subtype", meta["institution_subtype"])
        node.setdefault("confidence", meta["confidence"])
        node.setdefault("source", meta["source"])
        if node.get("external") is None:
            node["external"] = meta["entity_type"] != "INTERNAL_ACCOUNT"
    for edge in edges:
        edge.setdefault("relationship_type", edge.get("txn_id") and "TRANSFER" or "POSSIBLE_LINK")
        if edge.get("visibility") is None:
            edge["visibility"] = INFERRED if edge.get("relationship_type") == "POSSIBLE_LINK" else OBSERVED
        edge.setdefault("confidence", 1.0 if edge.get("visibility") == OBSERVED else 0.4)
        edge.setdefault("source", "ledger" if edge.get("visibility") == OBSERVED else "inference")
        edge.setdefault("evidence_ids", [f"E-TXN-{edge['txn_id']}"] if edge.get("txn_id") else [])
    banks = _institution_rollups(nodes, edges)
    boundaries = _boundary_nodes(nodes, edges)
    visibility = visibility_score(nodes, edges, boundaries)
    network["nodes"] = nodes
    network["edges"] = edges
    network["visibility"] = visibility
    network["boundaries"] = boundaries
    network["institutions"] = banks
    network["home_institution"] = home_institution()
    network["partial_network"] = visibility["unknown"]["boundaries"] > 0 or visibility["network_visibility_score"] < 0.85
    return network


def _institution_rollups(nodes: list[dict], edges: list[dict]) -> list[dict]:
    by_bank: dict[str, dict] = {}
    for node in nodes:
        bank = node.get("institution_id")
        if not bank:
            continue
        row = by_bank.setdefault(bank, {
            "institution_id": bank,
            "accounts": 0,
            "internal": bank == home_institution(),
            "visibility": OBSERVED,
            "note": "Institution appears in the visible graph. Not a finding of institutional criminality.",
        })
        row["accounts"] += 1
    for edge in edges:
        for key in ("origin_bank_id", "destination_bank_id"):
            bank = edge.get(key)
            if bank:
                by_bank.setdefault(bank, {
                    "institution_id": bank,
                    "accounts": 0,
                    "internal": bank == home_institution(),
                    "visibility": OBSERVED,
                    "note": "Institution appears in the visible graph. Not a finding of institutional criminality.",
                })
    return sorted(by_bank.values(), key=lambda r: r["institution_id"])


def _boundary_nodes(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """Unresolved or external hops at the edge of the observed graph."""
    inbound = Counter(e.get("target") for e in edges)
    outbound = Counter(e.get("source") for e in edges)
    out = []
    for i, node in enumerate(nodes, start=1):
        vis = node.get("visibility")
        internal = node.get("entity_type") == "INTERNAL_ACCOUNT"
        leaf = (inbound[node.get("id")] == 0) or (outbound[node.get("id")] == 0)
        if vis in {UNKNOWN, EXTERNAL} or (not internal and leaf):
            out.append({
                "boundary_id": f"BOUNDARY-{i:02d}",
                "account_id": node.get("id"),
                "visibility": vis or OBSERVED,
                "institution_id": node.get("institution_id"),
                "direction": "upstream" if outbound[node.get("id")] == 0 else "downstream",
                "description": (
                    "Unresolved network area beyond this institutional boundary."
                    if vis == UNKNOWN
                    else "External or counterparty account at the edge of the visible graph."
                ),
            })
    return out


def attach_unknown_boundary(network: dict, *, node_id: str, attach_to: str, direction: str = "downstream") -> dict:
    """Record an unknown hop. Does not invent a real institution or customer."""
    nodes = network.setdefault("nodes", [])
    if any(n.get("id") == node_id for n in nodes):
        return annotate_network(network)
    layer = max((int(n.get("layer") or 0) for n in nodes), default=0) + 1
    nodes.append({
        "id": node_id,
        "kind": "unknown_entity",
        "name": "unresolved boundary",
        "focus": False,
        "external": True,
        "visibility": UNKNOWN,
        "entity_type": "UNKNOWN_ENTITY",
        "institution_id": None,
        "confidence": 0.15,
        "source": "unresolved_boundary",
        "layer": layer,
    })
    source, target = (attach_to, node_id) if direction == "downstream" else (node_id, attach_to)
    network.setdefault("edges", []).append({
        "source": source,
        "target": target,
        "relationship_type": "POSSIBLE_LINK",
        "visibility": INFERRED,
        "confidence": 0.25,
        "source_kind": "inference",
        "source": "inference",
        "evidence_ids": [],
        "amount": None,
        "txn_id": None,
    })
    return annotate_network(network)
