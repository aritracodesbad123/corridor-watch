"""Institution-level aggregation. Neutral AML language only."""
from __future__ import annotations

import time

from db import connect, init_schema
from graph.visibility import home_institution


_CACHE: dict = {}


def list_institutions() -> list[dict]:
    now = time.time()
    cached = _CACHE.get("rows")
    if cached is not None and now - float(_CACHE.get("ts") or 0) < 20:
        return cached
    init_schema()
    con = connect()
    try:
        banks = {r["bank_id"]: dict(r) for r in con.execute("SELECT * FROM banks").fetchall()}
        acct = {
            r["bank_id"]: int(r["c"])
            for r in con.execute("SELECT bank_id, COUNT(*) AS c FROM accounts GROUP BY bank_id")
        }
        origin = [dict(r) for r in con.execute(
            """SELECT origin_bank_id AS bank_id, COUNT(*) AS transaction_count,
                      SUM(CASE WHEN risk_tier IN ('HIGH', 'CRITICAL') THEN 1 ELSE 0 END) AS suspicious_transaction_count,
                      COALESCE(SUM(CASE WHEN risk_tier IN ('HIGH', 'CRITICAL') THEN amount ELSE 0 END), 0) AS suspicious_transaction_amount
               FROM transactions WHERE origin_bank_id IS NOT NULL GROUP BY origin_bank_id"""
        )]
        dest = [dict(r) for r in con.execute(
            """SELECT destination_bank_id AS bank_id, COUNT(*) AS transaction_count,
                      SUM(CASE WHEN risk_tier IN ('HIGH', 'CRITICAL') THEN 1 ELSE 0 END) AS suspicious_transaction_count,
                      COALESCE(SUM(CASE WHEN risk_tier IN ('HIGH', 'CRITICAL') THEN amount ELSE 0 END), 0) AS suspicious_transaction_amount
               FROM transactions WHERE destination_bank_id IS NOT NULL GROUP BY destination_bank_id"""
        )]
    finally:
        con.close()
    home = home_institution()
    out = {}
    for bank_id, bank in banks.items():
        out[bank_id] = {
            "institution_id": bank_id,
            "name": bank.get("name"),
            "country": bank.get("country"),
            "institution_type": bank.get("institution_type"),
            "role": "home" if bank_id == home else "counterparty",
            "connected_accounts": acct.get(bank_id, 0),
            "transaction_count": 0,
            "suspicious_transaction_count": 0,
            "suspicious_transaction_amount": 0.0,
            "corridors": [],
            "note": "Presence in a suspicious graph is not a finding of institutional criminality.",
        }
    for row in origin + dest:
        bank = row.get("bank_id")
        if bank not in out:
            continue
        out[bank]["transaction_count"] += int(row.get("transaction_count") or 0)
        out[bank]["suspicious_transaction_count"] += int(row.get("suspicious_transaction_count") or 0)
        out[bank]["suspicious_transaction_amount"] += float(row.get("suspicious_transaction_amount") or 0)
    rows = []
    for row in out.values():
        row["suspicious_transaction_amount"] = round(row["suspicious_transaction_amount"], 2)
        row["exposure"] = "elevated_network_exposure" if row["suspicious_transaction_count"] else "routine"
        rows.append(row)
    rows.sort(key=lambda r: (-r["suspicious_transaction_count"], r["institution_id"]))
    _CACHE.update(ts=now, rows=rows)
    return rows


def institution_network(institution_id: str) -> dict:
    init_schema()
    con = connect()
    bank = con.execute("SELECT * FROM banks WHERE bank_id=?", (institution_id,)).fetchone()
    if not bank:
        con.close()
        return {"institution_id": institution_id, "found": False, "nodes": [], "edges": []}
    txns = [dict(r) for r in con.execute(
        """SELECT * FROM transactions
           WHERE origin_bank_id=? OR destination_bank_id=?
           ORDER BY ts DESC LIMIT 80""",
        (institution_id, institution_id),
    ).fetchall()]
    con.close()
    nodes = {}
    edges = []
    for t in txns:
        for nid in (t["sender_id"], t["receiver_id"]):
            nodes.setdefault(nid, {"id": nid, "kind": "account"})
        edges.append({
            "source": t["sender_id"],
            "target": t["receiver_id"],
            "txn_id": t["txn_id"],
            "amount": t["amount"],
            "corridor": t.get("corridor"),
            "relationship_type": "TRANSFER",
            "visibility": "observed",
        })
    return {
        "institution_id": institution_id,
        "found": True,
        "name": dict(bank).get("name"),
        "note": "Institution-level graph. Not a finding of institutional criminality.",
        "nodes": list(nodes.values()),
        "edges": edges,
        "transaction_count": len(txns),
    }
