"""
NetworkX graph features + named fraud-pattern scoring.

Features (per owned account):
  fan_in_count, fan_out_count, pass_through_ratio, avg_hold_time_minutes,
  shared_device_count, shared_beneficiary_count, multi_hop_chain_depth,
  account_age_days, corridor_velocity_score, behavioral_risk

Patterns classified: mule_pass_through, split_transaction_laundering,
shared_device_ring, synthetic_identity, multi_hop_chain.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime

import networkx as nx

from db import connect

NOW = datetime(2026, 9, 1)
FLAG_THRESHOLD = 40


def load(con):
    accounts = {r["account_id"]: dict(r) for r in con.execute("SELECT * FROM accounts")}
    txns = [dict(r) for r in con.execute("SELECT * FROM transactions")]
    devices = [dict(r) for r in con.execute("SELECT * FROM account_devices")]
    benefs = [dict(r) for r in con.execute("SELECT * FROM account_beneficiaries")]
    sessions = [dict(r) for r in con.execute("SELECT * FROM sessions")]
    return accounts, txns, devices, benefs, sessions


def build_graph(txns) -> nx.DiGraph:
    g = nx.DiGraph()
    for t in txns:
        # Keep multi-edge amounts as list on a single directed edge summary
        if g.has_edge(t["sender_id"], t["receiver_id"]):
            g[t["sender_id"]][t["receiver_id"]]["amounts"].append(t["amount"])
            g[t["sender_id"]][t["receiver_id"]]["tss"].append(t["ts"])
            g[t["sender_id"]][t["receiver_id"]]["txn_ids"].append(t["txn_id"])
        else:
            g.add_edge(
                t["sender_id"], t["receiver_id"],
                amounts=[t["amount"]], tss=[t["ts"]], txn_ids=[t["txn_id"]],
                amount=t["amount"], ts=t["ts"], txn_id=t["txn_id"],
            )
    return g


def account_age_days(accounts, acc_id) -> int:
    a = accounts.get(acc_id)
    if not a:
        return 9999
    return (NOW - datetime.fromisoformat(a["opened_date"])).days


def pass_through_ratio(g, node) -> float:
    inflow = sum(sum(d.get("amounts", [d.get("amount", 0)])) for _, _, d in g.in_edges(node, data=True))
    outflow = sum(sum(d.get("amounts", [d.get("amount", 0)])) for _, _, d in g.out_edges(node, data=True))
    if inflow == 0:
        return 0.0
    return min(outflow / inflow, 1.5)


def avg_hold_time_minutes(g, node) -> float:
    in_ts = []
    out_ts = []
    for _, _, d in g.in_edges(node, data=True):
        in_ts.extend(d.get("tss", [d.get("ts")]))
    for _, _, d in g.out_edges(node, data=True):
        out_ts.extend(d.get("tss", [d.get("ts")]))
    if not in_ts or not out_ts:
        return 99999.0
    in_times = sorted(datetime.fromisoformat(t) for t in in_ts if t)
    out_times = sorted(datetime.fromisoformat(t) for t in out_ts if t)
    holds = []
    for ot in out_times:
        prior = [it for it in in_times if it <= ot]
        if prior:
            holds.append((ot - max(prior)).total_seconds() / 60.0)
    return round(sum(holds) / len(holds), 1) if holds else 99999.0


def shared_counts(account_id, mapping) -> int:
    """How many other accounts share any key (device/beneficiary) with this account."""
    keys = mapping["by_account"].get(account_id, set())
    peers = set()
    for k in keys:
        peers |= mapping["by_key"].get(k, set())
    peers.discard(account_id)
    return len(peers)


def build_share_maps(rows, account_key, share_key):
    by_account = defaultdict(set)
    by_key = defaultdict(set)
    for r in rows:
        by_account[r[account_key]].add(r[share_key])
        by_key[r[share_key]].add(r[account_key])
    return {"by_account": by_account, "by_key": by_key}


def multi_hop_depth(g, node, max_depth=5) -> int:
    """Longest simple outbound path length from node (capped)."""
    if node not in g:
        return 0
    best = 0
    for target in list(g.nodes())[:]:
        if target == node:
            continue
        try:
            length = nx.shortest_path_length(g, node, target)
            if length > best:
                best = length
                if best >= max_depth:
                    return max_depth
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
    return best


def corridor_velocity(txns_by_account, account_id) -> float:
    rows = txns_by_account.get(account_id, [])
    if len(rows) < 2:
        return 0.0
    times = sorted(datetime.fromisoformat(t["ts"]) for t in rows)
    span_hours = max((times[-1] - times[0]).total_seconds() / 3600.0, 0.25)
    return round(len(rows) / span_hours, 2)


def behavioral_risk(sessions_by_account, account_id) -> float:
    rows = sessions_by_account.get(account_id, [])
    if not rows:
        return 0.0
    scores = []
    for s in rows:
        scores.append(
            s["bot_likelihood"] * 40
            + s["copy_paste_risk"] * 25
            + min(s["typing_deviation"], 4) * 5
            + min(s["navigation_velocity"], 6) * 3
            + (15 if s["geo_mismatch"] else 0)
        )
    return round(min(max(scores), 100), 1)


def pattern_scores(features: dict, account: dict) -> dict[str, float]:
    age = features["account_age_days"]
    ptr = features["pass_through_ratio"]
    fan_in = features["fan_in_count"]
    hold = features["avg_hold_time_minutes"]
    shared_dev = features["shared_device_count"]
    shared_ben = features["shared_beneficiary_count"]
    hop = features["multi_hop_chain_depth"]
    vel = features["corridor_velocity_score"]
    beh = features["behavioral_risk"]
    income = account.get("stated_income_usd") or 0
    occ = (account.get("occupation") or "").lower()

    mule = min(100, fan_in * 8 + ptr * 35 + (25 if hold < 180 else 0) + (15 if age <= 7 else 0))
    # ponytail: source-only velocity is disbursement (payroll/treasury), not smurf
    inbound = fan_in >= 3 or ptr >= 0.3
    split_vel = vel * 8 if inbound else 0.0
    split = min(100, fan_in * 7 + shared_ben * 12 + split_vel + (10 if age <= 30 and inbound else 0))
    shared = min(100, shared_dev * 18 + beh * 0.35 + (20 if age <= 14 else 0))
    synth = 0
    if age <= 7:
        synth += 35
    if occ in {"unemployed", "student", "intern"}:
        synth += 25
    if income < 5000:
        synth += 20
    synth += beh * 0.2
    synth = min(100, synth)
    multi = min(100, hop * 18 + ptr * 20 + (15 if hold < 360 else 0) + beh * 0.15)

    return {
        "mule_pass_through": round(mule, 1),
        "split_transaction_laundering": round(split, 1),
        "shared_device_ring": round(shared, 1),
        "synthetic_identity": round(synth, 1),
        "multi_hop_chain": round(multi, 1),
    }


def composite_score(features: dict, patterns: dict) -> tuple[float, str]:
    base = 0
    base += min(features["fan_in_count"] * 5, 25)
    base += min(features["pass_through_ratio"] * 30, 30)
    base += 15 if features["account_age_days"] <= 7 else (8 if features["account_age_days"] <= 30 else 0)
    base += min(features["shared_device_count"] * 8, 20)
    base += min(features["behavioral_risk"] * 0.2, 15)
    base += 10 if features["avg_hold_time_minutes"] < 180 else 0
    primary = max(patterns, key=patterns.get)
    score = round(min(max(base, patterns[primary] * 0.85), 100), 1)
    return score, primary if patterns[primary] >= 35 else "elevated_activity"


def score_all(con):
    accounts, txns, devices, benefs, sessions = load(con)
    g = build_graph(txns)
    device_map = build_share_maps(devices, "account_id", "device_id")
    benef_map = build_share_maps(benefs, "account_id", "beneficiary_id")

    txns_by_account = defaultdict(list)
    for t in txns:
        if t["sender_id"] in accounts:
            txns_by_account[t["sender_id"]].append(t)
        if t["receiver_id"] in accounts:
            txns_by_account[t["receiver_id"]].append(t)

    sessions_by_account = defaultdict(list)
    for s in sessions:
        sessions_by_account[s["account_id"]].append(s)

    scores = {}
    for node in list(accounts.keys()):
        if node not in g:
            # still score dormant/new accounts with sessions only
            feats = {
                "fan_in_count": 0,
                "fan_out_count": 0,
                "pass_through_ratio": 0.0,
                "avg_hold_time_minutes": 99999.0,
                "shared_device_count": shared_counts(node, device_map),
                "shared_beneficiary_count": shared_counts(node, benef_map),
                "multi_hop_chain_depth": 0,
                "account_age_days": account_age_days(accounts, node),
                "corridor_velocity_score": 0.0,
                "behavioral_risk": behavioral_risk(sessions_by_account, node),
            }
        else:
            feats = {
                "fan_in_count": g.in_degree(node),
                "fan_out_count": g.out_degree(node),
                "pass_through_ratio": round(pass_through_ratio(g, node), 2),
                "avg_hold_time_minutes": avg_hold_time_minutes(g, node),
                "shared_device_count": shared_counts(node, device_map),
                "shared_beneficiary_count": shared_counts(node, benef_map),
                "multi_hop_chain_depth": multi_hop_depth(g, node),
                "account_age_days": account_age_days(accounts, node),
                "corridor_velocity_score": corridor_velocity(txns_by_account, node),
                "behavioral_risk": behavioral_risk(sessions_by_account, node),
            }
        patterns = pattern_scores(feats, accounts[node])
        risk, primary = composite_score(feats, patterns)
        scores[node] = {
            **feats,
            "risk_score": risk,
            "primary_pattern": primary,
            "pattern_scores": json.dumps(patterns),
        }
    return scores, txns, g


def write_scores(con, scores, txns):
    con.execute("DELETE FROM risk_scores")
    con.execute("DELETE FROM flagged_transactions")
    rows = [{"account_id": k, **v} for k, v in scores.items()]
    con.executemany(
        """INSERT INTO risk_scores (
            account_id, risk_score, fan_in_count, fan_out_count, pass_through_ratio,
            avg_hold_time_minutes, shared_device_count, shared_beneficiary_count,
            multi_hop_chain_depth, account_age_days, corridor_velocity_score,
            behavioral_risk, primary_pattern, pattern_scores
        ) VALUES (
            :account_id, :risk_score, :fan_in_count, :fan_out_count, :pass_through_ratio,
            :avg_hold_time_minutes, :shared_device_count, :shared_beneficiary_count,
            :multi_hop_chain_depth, :account_age_days, :corridor_velocity_score,
            :behavioral_risk, :primary_pattern, :pattern_scores
        )""",
        rows,
    )

    flagged = []
    for t in txns:
        s = scores.get(t["sender_id"], {}).get("risk_score", 0)
        r = scores.get(t["receiver_id"], {}).get("risk_score", 0)
        risk = max(s, r)
        if risk < FLAG_THRESHOLD:
            continue
        if s >= r:
            pattern = scores.get(t["sender_id"], {}).get("primary_pattern", "elevated_activity")
        else:
            pattern = scores.get(t["receiver_id"], {}).get("primary_pattern", "elevated_activity")
        flagged.append({
            "txn_id": t["txn_id"],
            "sender_id": t["sender_id"],
            "receiver_id": t["receiver_id"],
            "amount": t["amount"],
            "corridor": t["corridor"],
            "ts": t["ts"],
            "risk_score": risk,
            "primary_pattern": pattern,
            "fraud_scenario": t.get("fraud_scenario") or "normal",
            "currency": t.get("currency") or "USD",
            "purpose": t.get("purpose") or "",
            "source_of_funds": t.get("source_of_funds") or "",
        })
    con.executemany(
        """INSERT INTO flagged_transactions (
            txn_id, sender_id, receiver_id, amount, corridor, ts, risk_score,
            primary_pattern, fraud_scenario, currency, purpose, source_of_funds
        ) VALUES (
            :txn_id, :sender_id, :receiver_id, :amount, :corridor, :ts, :risk_score,
            :primary_pattern, :fraud_scenario, :currency, :purpose, :source_of_funds
        )""",
        flagged,
    )
    con.commit()
    return len(flagged)


# Approximate centroids for corridor map (lat, lon)
COUNTRY_COORDS = {
    "IN": {"lat": 21.0, "lon": 78.0, "label": "India"},
    "PH": {"lat": 12.5, "lon": 122.0, "label": "Philippines"},
    "ID": {"lat": -2.0, "lon": 118.0, "label": "Indonesia"},
    "VN": {"lat": 16.0, "lon": 108.0, "label": "Vietnam"},
    "SG": {"lat": 1.35, "lon": 103.8, "label": "Singapore"},
    "AE": {"lat": 24.3, "lon": 54.4, "label": "UAE"},
    "US": {"lat": 39.5, "lon": -98.0, "label": "United States"},
    "??": {"lat": 8.0, "lon": 70.0, "label": "Unknown origin"},
}


def _parse_corridor(corridor: str) -> tuple[str, str]:
    if not corridor or "->" not in corridor:
        return ("??", "??")
    src, dst = corridor.split("->", 1)
    return (src.strip() or "??", dst.strip() or "??")


def _infer_country(account_id: str, accounts: dict, edge_corridor: str | None, side: str) -> str:
    acc = accounts.get(account_id)
    if acc and acc.get("country"):
        return acc["country"]
    src, dst = _parse_corridor(edge_corridor or "")
    return src if side == "sender" else dst


def _collect_related_txns(con, seed_ids: set[str], hops: int = 2, limit: int = 80) -> list[dict]:
    """BFS expand transaction neighborhood so mule/multi-hop chains are visible."""
    seen_txn = set()
    frontier = set(seed_ids)
    known = set(seed_ids)
    collected: list[dict] = []
    for _ in range(hops):
        if not frontier or len(collected) >= limit:
            break
        placeholders = ",".join("?" * len(frontier))
        params = list(frontier) + list(frontier)
        rows = con.execute(
            f"""SELECT * FROM transactions
                WHERE sender_id IN ({placeholders}) OR receiver_id IN ({placeholders})
                ORDER BY ts ASC LIMIT ?""",
            params + [limit],
        ).fetchall()
        next_frontier = set()
        for row in rows:
            r = dict(row)
            if r["txn_id"] in seen_txn:
                continue
            seen_txn.add(r["txn_id"])
            collected.append(r)
            for nid in (r["sender_id"], r["receiver_id"]):
                if nid not in known:
                    next_frontier.add(nid)
                    known.add(nid)
        frontier = next_frontier
    collected.sort(key=lambda x: x.get("ts") or "")
    return collected[:limit]


def _layer_accounts(edges: list[dict], focus_sender: str) -> dict[str, int]:
    """Assign left-to-right DAG layers from earliest sources toward sinks."""
    from collections import defaultdict, deque

    children = defaultdict(set)
    parents = defaultdict(set)
    nodes = set()
    for e in edges:
        children[e["source"]].add(e["target"])
        parents[e["target"]].add(e["source"])
        nodes.add(e["source"])
        nodes.add(e["target"])

    # Kahn-like longest-path layering from roots (prefer focus sender as root)
    indeg = {n: len(parents[n]) for n in nodes}
    roots = [n for n in nodes if indeg[n] == 0]
    if focus_sender in nodes and focus_sender not in roots:
        roots.insert(0, focus_sender)
    if not roots and nodes:
        roots = [focus_sender] if focus_sender in nodes else [next(iter(nodes))]

    layer = {n: 0 for n in nodes}
    q = deque(roots)
    seen = set(roots)
    while q:
        u = q.popleft()
        for v in children[u]:
            layer[v] = max(layer.get(v, 0), layer[u] + 1)
            if v not in seen:
                seen.add(v)
                q.append(v)
    # orphan nodes
    for n in nodes:
        layer.setdefault(n, 0)
    return layer


def network_subgraph(txn_id: str, depth: int = 2) -> dict:
    """Nodes/edges + money-flow DAG layers + country corridor map for the UI."""
    con = connect()
    t = con.execute("SELECT * FROM transactions WHERE txn_id=?", (txn_id,)).fetchone()
    if not t:
        # fallback: flagged row only
        t = con.execute("SELECT * FROM flagged_transactions WHERE txn_id=?", (txn_id,)).fetchone()
    if not t:
        con.close()
        return {"nodes": [], "edges": [], "flow_dag": {"nodes": [], "edges": []}, "geo": {"countries": [], "flows": []}}

    t = dict(t)
    focus = {t["sender_id"], t["receiver_id"]}
    accounts = {r["account_id"]: dict(r) for r in con.execute("SELECT * FROM accounts")}
    scores = {r["account_id"]: dict(r) for r in con.execute("SELECT * FROM risk_scores")}
    related = _collect_related_txns(con, focus, hops=depth, limit=80)
    con.close()

    # Ensure focal txn is present
    if not any(r["txn_id"] == txn_id for r in related):
        related.append(t)
        related.sort(key=lambda x: x.get("ts") or "")

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    for r in related:
        src_c = _infer_country(r["sender_id"], accounts, r.get("corridor"), "sender")
        dst_c = _infer_country(r["receiver_id"], accounts, r.get("corridor"), "receiver")
        for nid, country in ((r["sender_id"], src_c), (r["receiver_id"], dst_c)):
            if nid not in nodes:
                acc = accounts.get(nid, {})
                rs = scores.get(nid, {})
                nodes[nid] = {
                    "id": nid,
                    "name": acc.get("name") or ("external" if str(nid).startswith("EXT") else nid),
                    "country": country,
                    "risk_score": rs.get("risk_score", 0),
                    "pattern": rs.get("primary_pattern", "external" if str(nid).startswith("EXT") else "elevated_activity"),
                    "focus": nid in focus,
                    "external": str(nid).startswith("EXT") or nid not in accounts,
                    "institution_id": acc.get("bank_id"),
                }
            else:
                # keep strongest country signal
                if nodes[nid]["country"] in ("??", None) and country != "??":
                    nodes[nid]["country"] = country
        edges.append({
            "source": r["sender_id"],
            "target": r["receiver_id"],
            "amount": r["amount"],
            "txn_id": r["txn_id"],
            "ts": r.get("ts"),
            "corridor": r.get("corridor") or f"{src_c}->{dst_c}",
            "highlight": r["txn_id"] == txn_id,
            "fraud_scenario": r.get("fraud_scenario") or "normal",
        })

    layers = _layer_accounts(edges, t["sender_id"])
    for nid, node in nodes.items():
        node["layer"] = layers.get(nid, 0)

    # Geo corridor aggregation
    flow_map: dict[tuple[str, str], dict] = {}
    country_stats: dict[str, dict] = {}
    for e in edges:
        src_c = nodes[e["source"]]["country"]
        dst_c = nodes[e["target"]]["country"]
        if src_c == dst_c:
            # still show if corridor string disagrees
            cs, cd = _parse_corridor(e.get("corridor") or "")
            if cs != cd:
                src_c, dst_c = cs, cd
        key = (src_c, dst_c)
        bucket = flow_map.setdefault(key, {
            "source": src_c, "target": dst_c, "amount": 0.0, "count": 0, "highlight": False,
        })
        bucket["amount"] += float(e["amount"] or 0)
        bucket["count"] += 1
        bucket["highlight"] = bucket["highlight"] or e["highlight"]
        for c in (src_c, dst_c):
            st = country_stats.setdefault(c, {"country": c, "in_amount": 0.0, "out_amount": 0.0, "accounts": set()})
            if c == src_c:
                st["out_amount"] += float(e["amount"] or 0)
                st["accounts"].add(e["source"])
            if c == dst_c:
                st["in_amount"] += float(e["amount"] or 0)
                st["accounts"].add(e["target"])

    countries = []
    for c, st in country_stats.items():
        coords = COUNTRY_COORDS.get(c, COUNTRY_COORDS["??"])
        countries.append({
            "country": c,
            "label": coords["label"] if c in COUNTRY_COORDS else c,
            "lat": coords["lat"],
            "lon": coords["lon"],
            "in_amount": round(st["in_amount"], 2),
            "out_amount": round(st["out_amount"], 2),
            "account_count": len(st["accounts"]),
            "focus": any(nodes[n]["focus"] and nodes[n]["country"] == c for n in nodes),
        })

    flows = []
    for (src, dst), bucket in flow_map.items():
        if src == dst:
            continue
        flows.append({
            **bucket,
            "amount": round(bucket["amount"], 2),
            "source_lat": COUNTRY_COORDS.get(src, COUNTRY_COORDS["??"])["lat"],
            "source_lon": COUNTRY_COORDS.get(src, COUNTRY_COORDS["??"])["lon"],
            "target_lat": COUNTRY_COORDS.get(dst, COUNTRY_COORDS["??"])["lat"],
            "target_lon": COUNTRY_COORDS.get(dst, COUNTRY_COORDS["??"])["lon"],
        })

    node_list = list(nodes.values())
    payload = {
        "nodes": node_list,
        "edges": edges,
        "focus_txn_id": txn_id,
        "flow_dag": {
            "nodes": node_list,
            "edges": edges,
            "max_layer": max((n["layer"] for n in node_list), default=0),
        },
        "geo": {
            "countries": countries,
            "flows": flows,
        },
    }
    try:
        from graph.visibility import annotate_network
        intel_refs = set()
        try:
            from intelligence.repository import referenced_entities
            intel_refs = referenced_entities()
        except Exception:
            intel_refs = set()
        annotate_network(payload, accounts=accounts, intel_refs=intel_refs)
        payload["flow_dag"]["nodes"] = payload["nodes"]
        payload["flow_dag"]["edges"] = payload["edges"]
        payload["flow_dag"]["max_layer"] = max((int(n.get("layer") or 0) for n in payload["nodes"]), default=0)
    except Exception:
        pass
    return payload


if __name__ == "__main__":
    con = connect()
    scores, txns, _ = score_all(con)
    n = write_scores(con, scores, txns)
    con.close()
    print(f"scored {len(scores)} accounts, flagged {n} transactions")
