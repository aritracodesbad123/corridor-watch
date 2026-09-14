"""Match a live network against the Crime Pattern DNA library."""
from __future__ import annotations

import json
import uuid

from db import connect, init_schema
from metrics import METRICS
from patterns.repository import list_patterns
from pubsub.schemas import utc_now


def observed_signals(txn: dict, network: dict, risk: dict | None = None) -> set[str]:
    signals: set[str] = set()
    features = (network or {}).get("features") or {}
    risk = risk or {}
    if features.get("fan_in", 0) >= 4:
        signals.update({"incoming_spike", "fan_in"})
    if features.get("fan_out", 0) >= 2:
        signals.add("rapid_fanout")
    if features.get("shared_device_groups", 0) >= 1:
        signals.add("shared_device")
    if features.get("shared_beneficiary_groups", 0) >= 1:
        signals.add("shared_beneficiary")
    if features.get("cross_border", 0) >= 1:
        signals.add("cross_border")
    if features.get("institution_count", 0) >= 3:
        signals.update({"cross_institution", "multi_hop", "owned_intermediates"})
    if (txn.get("origin_country") == "??") or (txn.get("corridor") or "").startswith("??"):
        signals.add("unknown_origin")
    age = risk.get("account_age_days")
    if age is not None and int(age) <= 7:
        signals.update({"new_account", "young_account", "short_account_life"})
    hold = risk.get("avg_hold_time_minutes")
    if hold is not None and float(hold) < 180:
        signals.add("short_hold_period")
    ptr = risk.get("pass_through_ratio")
    if ptr is not None and float(ptr) >= 0.9:
        signals.add("high_pass_through")
    if features.get("txn_count", 0) >= 3:
        signals.add("burst_send")
    return signals


def match_patterns(txn: dict, network: dict, risk: dict | None = None, *, persist: bool = True) -> list[dict]:
    signals = observed_signals(txn, network, risk)
    matches = []
    for pattern in list_patterns():
        if not pattern.active:
            continue
        overlap = signals & pattern.all_signals()
        universe = pattern.all_signals() or {"_"}
        score = len(overlap) / len(universe)
        if score < 0.35 and not overlap:
            continue
        if score < 0.35:
            continue
        vis = ((network or {}).get("visibility") or {})
        matches.append({
            "pattern_id": pattern.pattern_id,
            "name": pattern.name,
            "version": pattern.version,
            "score": round(score, 3),
            "pattern_match_score": round(score, 3),
            "match_strength": round(score * 100),
            "institutional_scope": getattr(pattern, "institutional_scope", "LOCAL"),
            "visibility": vis.get("network_visibility_score"),
            "evidence_coverage": round(score, 3),
            "matched_signals": sorted(overlap),
            "missing_signals": sorted(universe - overlap),
            "missing_expected_signals": sorted(universe - overlap),
            "evidence": [
                {
                    "evidence_id": f"P-{pattern.pattern_id}-{sig}",
                    "type": "pattern_signal",
                    "description": f"Observed signal '{sig}' matches {pattern.pattern_id}",
                    "source": "crime_pattern_dna",
                    "source_ref": pattern.pattern_id,
                    "confidence": 1.0,
                }
                for sig in sorted(overlap)
            ],
        })
    matches.sort(key=lambda m: m["score"], reverse=True)
    if matches:
        METRICS.inc("pattern_matches_total", len(matches))
        if persist:
            _persist_matches(txn.get("txn_id", ""), matches)
    return matches


def _persist_matches(txn_id: str, matches: list[dict]) -> None:
    if not txn_id:
        return
    init_schema()
    con = connect()
    for match in matches[:8]:
        con.execute(
            """INSERT INTO pattern_matches (match_id, pattern_id, txn_id, case_id, score, evidence, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                f"M-{uuid.uuid4().hex[:10]}",
                match["pattern_id"],
                txn_id,
                txn_id,
                match["score"],
                json.dumps(match["evidence"]),
                utc_now(),
            ),
        )
    con.commit()
    con.close()
