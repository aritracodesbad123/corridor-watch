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
            """SELECT corridor,
                      COALESCE(SUM(amount), 0) AS volume,
                      COUNT(*) AS count,
                      SUM(CASE WHEN risk_tier IN ('HIGH', 'CRITICAL') THEN 1 ELSE 0 END) AS suspicious_count
               FROM transactions
               GROUP BY corridor"""
        ).fetchall()]
        accounts: dict[str, int] = {}
        patterns: dict[str, list[str]] = {}
        for r in con.execute(
            """SELECT corridor, primary_pattern FROM flagged_transactions
               WHERE primary_pattern IS NOT NULL AND primary_pattern != ''
               GROUP BY corridor, primary_pattern"""
        ):
            patterns.setdefault(r["corridor"], []).append(r["primary_pattern"])
        networks: dict[str, int] = {}
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
    try:
        flagged_n = int(con.execute("SELECT COUNT(*) AS c FROM flagged_transactions").fetchone()["c"])
        network_n = int(con.execute(
            """SELECT COUNT(*) AS c FROM (
                   SELECT network_id FROM flagged_transactions
                   WHERE network_id IS NOT NULL AND network_id != ''
                   UNION
                   SELECT network_id FROM investigation_queue
                   WHERE network_id IS NOT NULL AND network_id != ''
               ) n"""
        ).fetchone()["c"])
    finally:
        con.close()
    if not network_n:
        network_n = flagged_n
    return {
        "flagged_transactions": flagged_n,
        "baseline_items_reviewed": flagged_n,
        "network_items_reviewed": network_n or flagged_n,
        "network_investigations": network_n,
        "compression_ratio": round(flagged_n / network_n, 2) if network_n else None,
        "unit_of_work": "network_investigation",
        "note": "Traditional review counts flagged wires. Corridor Watch reviews the collapsed network. Measured, not claimed.",
    }
