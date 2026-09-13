"""Institution-level aggregation. Neutral AML language only."""
from __future__ import annotations

from db import connect, init_schema
from graph.visibility import home_institution


def list_institutions() -> list[dict]:
    init_schema()
    con = connect()
    banks = {r["bank_id"]: dict(r) for r in con.execute("SELECT * FROM banks").fetchall()}
    txns = [dict(r) for r in con.execute(
        "SELECT origin_bank_id, destination_bank_id, amount, risk_tier, corridor, fraud_scenario FROM transactions"
    ).fetchall()]
    accounts = [dict(r) for r in con.execute("SELECT account_id, bank_id FROM accounts").fetchall()]
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
            "connected_accounts": 0,
            "transaction_count": 0,
            "suspicious_transaction_count": 0,
            "suspicious_transaction_amount": 0.0,
            "corridors": set(),
            "note": "Presence in a suspicious graph is not a finding of institutional criminality.",
        }
    for acc in accounts:
        bank = acc.get("bank_id")
        if bank in out:
            out[bank]["connected_accounts"] += 1
    for t in txns:
        for bank in (t.get("origin_bank_id"), t.get("destination_bank_id")):
            if bank not in out:
                continue
            out[bank]["transaction_count"] += 1
            if t.get("corridor"):
                out[bank]["corridors"].add(t["corridor"])
            if t.get("risk_tier") in {"HIGH", "CRITICAL"} or (t.get("fraud_scenario") or "normal") != "normal":
                out[bank]["suspicious_transaction_count"] += 1
                out[bank]["suspicious_transaction_amount"] += float(t.get("amount") or 0)
    for row in out.values():
        row["corridors"] = sorted(row["corridors"])
        row["suspicious_transaction_amount"] = round(row["suspicious_transaction_amount"], 2)
        row["exposure"] = "elevated_network_exposure" if row["suspicious_transaction_count"] else "routine"
    return sorted(out.values(), key=lambda r: (-r["suspicious_transaction_count"], r["institution_id"]))


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
