"""Corridor-level intelligence. A corridor is a first-class object."""
from __future__ import annotations

import time

from db import connect, init_schema

_CORRIDOR_CACHE: dict = {"ts": 0.0, "rows": None}


def corridor_intelligence(limit: int = 40) -> list[dict]:
    now = time.time()
    cached = _CORRIDOR_CACHE.get("rows")
    if cached is not None and now - float(_CORRIDOR_CACHE.get("ts") or 0) < 20:
        return cached[:limit]
    init_schema()
    con = connect()
    try:
        stats = [dict(r) for r in con.execute(
            """SELECT t.corridor AS corridor,
                      COALESCE(SUM(t.amount), 0) AS volume,
                      COUNT(*) AS count,
                      SUM(CASE WHEN t.risk_tier IN ('HIGH', 'CRITICAL')
                                OR COALESCE(t.fraud_scenario, 'normal') != 'normal'
                                OR f.txn_id IS NOT NULL
                               THEN 1 ELSE 0 END) AS suspicious_count
               FROM transactions t
               LEFT JOIN flagged_transactions f ON f.txn_id = t.txn_id
               GROUP BY t.corridor"""
        ).fetchall()]
        accounts = {
            r["corridor"]: int(r["unique_accounts"])
            for r in con.execute(
                """SELECT corridor, COUNT(*) AS unique_accounts FROM (
                       SELECT corridor, sender_id AS aid FROM transactions
                       UNION
                       SELECT corridor, receiver_id AS aid FROM transactions
                   ) u GROUP BY corridor"""
            )
        }
        patterns: dict[str, list[str]] = {}
        for r in con.execute(
            """SELECT corridor, fraud_scenario FROM transactions
               WHERE fraud_scenario IS NOT NULL AND fraud_scenario != 'normal'
               GROUP BY corridor, fraud_scenario"""
        ):
            patterns.setdefault(r["corridor"], []).append(r["fraud_scenario"])
        networks = {
            r["corridor"]: int(r["network_count"])
            for r in con.execute(
                """SELECT corridor, COUNT(DISTINCT network_id) AS network_count FROM (
                       SELECT t.corridor AS corridor, q.network_id AS network_id
                       FROM investigation_queue q
                       JOIN transactions t ON t.txn_id = q.txn_id
                       WHERE q.network_id IS NOT NULL AND q.network_id != ''
                       UNION
                       SELECT corridor, network_id FROM flagged_transactions
                       WHERE network_id IS NOT NULL AND network_id != ''
                   ) n GROUP BY corridor"""
            )
        }
    finally:
        con.close()

    rows = []
    for s in stats:
        corridor = s.get("corridor") or "??->??"
        count = int(s.get("count") or 0)
        suspicious = int(s.get("suspicious_count") or 0)
        rows.append({
            "corridor": corridor,
            "origin": corridor.split("->")[0] if "->" in corridor else "??",
            "destination": corridor.split("->")[-1] if "->" in corridor else "??",
            "volume": round(float(s.get("volume") or 0), 2),
            "count": count,
            "suspicious_count": suspicious,
            "suspicious_rate": round(suspicious / (count or 1), 4),
            "unique_accounts": accounts.get(corridor, 0),
            "network_count": networks.get(corridor, 0),
            "patterns": sorted(patterns.get(corridor, [])),
            "risk": "high" if count and suspicious / count >= 0.15 else ("medium" if suspicious else "low"),
        })
    rows.sort(key=lambda r: (r["suspicious_count"], r["volume"]), reverse=True)
    _CORRIDOR_CACHE.update(ts=now, rows=rows)
    return rows[:limit]


def investigation_compression(txn_id: str | None = None) -> dict:
    """Related flagged events collapse into fewer network investigations."""
    init_schema()
    con = connect()
    flagged = [dict(r) for r in con.execute(
        "SELECT txn_id, sender_id, receiver_id, network_id FROM flagged_transactions"
    ).fetchall()]
    queued = [dict(r) for r in con.execute("SELECT txn_id, network_id FROM investigation_queue").fetchall()]
    con.close()
    networks = {q["network_id"] for q in queued if q.get("network_id")}
    networks.update(f.get("network_id") for f in flagged if f.get("network_id"))
    if not networks and flagged:
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            parent.setdefault(x, x)
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        for f in flagged:
            a, b = f["sender_id"], f["receiver_id"]
            parent.setdefault(a, a)
            parent.setdefault(b, b)
            parent[find(a)] = find(b)
        networks = {find(f["sender_id"]) for f in flagged}
    flagged_n = len(flagged)
    network_n = len(networks)
    return {
        "flagged_transactions": flagged_n,
        "baseline_items_reviewed": flagged_n,
        "network_items_reviewed": network_n or flagged_n,
        "network_investigations": network_n,
        "compression_ratio": round(flagged_n / network_n, 2) if network_n else None,
        "unit_of_work": "network_investigation",
        "note": "Traditional review counts flagged wires. Corridor Watch reviews the collapsed network. Measured, not claimed.",
    }
