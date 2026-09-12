"""Bounded graph construction — never rebuilds the full universe per event."""
from __future__ import annotations

from datetime import datetime, timedelta

from config import get_settings
from db import connect


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def collect_bounded_txns(
    seed_accounts: set[str],
    *,
    focus_ts: str | None = None,
    max_hops: int | None = None,
    lookback_minutes: int | None = None,
    lookahead_minutes: int | None = None,
    max_nodes: int | None = None,
    max_edges: int | None = None,
) -> list[dict]:
    settings = get_settings()
    max_hops = max_hops if max_hops is not None else settings.graph_max_hops
    lookback_minutes = lookback_minutes if lookback_minutes is not None else settings.graph_lookback_minutes
    lookahead_minutes = lookahead_minutes if lookahead_minutes is not None else settings.graph_lookahead_minutes
    max_nodes = max_nodes if max_nodes is not None else settings.max_investigation_size
    max_edges = max_edges if max_edges is not None else settings.max_investigation_edges

    center = _parse(focus_ts)
    start = (center - timedelta(minutes=lookback_minutes)).isoformat() if center else None
    end = (center + timedelta(minutes=lookahead_minutes)).isoformat() if center else None

    con = connect()
    seen_txn: set[str] = set()
    known = set(seed_accounts)
    frontier = set(seed_accounts)
    collected: list[dict] = []
    for _ in range(max_hops):
        if not frontier or len(collected) >= max_edges or len(known) >= max_nodes:
            break
        placeholders = ",".join("?" * len(frontier))
        params: list = list(frontier) + list(frontier)
        sql = (
            f"SELECT * FROM transactions WHERE sender_id IN ({placeholders}) "
            f"OR receiver_id IN ({placeholders})"
        )
        if start and end:
            sql += " AND ts>=? AND ts<=?"
            params.extend([start, end])
        sql += " ORDER BY ts ASC LIMIT ?"
        params.append(max_edges)
        rows = con.execute(sql, params).fetchall()
        next_frontier: set[str] = set()
        for row in rows:
            r = dict(row)
            if r["txn_id"] in seen_txn:
                continue
            seen_txn.add(r["txn_id"])
            collected.append(r)
            for nid in (r["sender_id"], r["receiver_id"]):
                if nid not in known and len(known) < max_nodes:
                    next_frontier.add(nid)
                    known.add(nid)
            if len(collected) >= max_edges:
                break
        frontier = next_frontier
    con.close()
    return collected[:max_edges]
