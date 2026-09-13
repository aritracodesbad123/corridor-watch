from __future__ import annotations

import json

from db import connect, init_schema, upsert
from patterns.schema import SEED_PATTERNS, CrimePatternDNA
from pubsub.schemas import utc_now


def _row_to_pattern(row: dict) -> CrimePatternDNA:
    def _loads(raw):
        if not raw:
            return []
        if isinstance(raw, list):
            return raw
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []

    return CrimePatternDNA(
        pattern_id=row["pattern_id"],
        version=int(row.get("version") or 1),
        name=row["name"],
        description=row.get("description") or "",
        entry_signals=_loads(row.get("entry_signals")),
        movement_signals=_loads(row.get("movement_signals")),
        relationship_signals=_loads(row.get("relationship_signals")),
        geography_signals=_loads(row.get("geography_signals")),
        timing_signals=_loads(row.get("timing_signals")),
        exit_signals=_loads(row.get("exit_signals")),
        graph_signature=row.get("graph_signature") or "",
        temporal_signature=row.get("temporal_signature") or "",
        corridor_signature=row.get("corridor_signature") or "",
        created_by=row.get("created_by") or "system",
        active=bool(row.get("active", 1)),
        confirmed_cases=int(row.get("confirmed_cases") or 0),
        institutional_scope=row.get("institutional_scope") or (
            "CROSS_INSTITUTION" if row.get("pattern_id") in {"CW-005", "CW-006", "CW-007"} else "LOCAL"
        ),
    )


def seed_library() -> int:
    init_schema()
    con = connect()
    for pattern in SEED_PATTERNS:
        existing = con.execute(
            "SELECT pattern_id FROM crime_patterns WHERE pattern_id=?",
            (pattern.pattern_id,),
        ).fetchone()
        if existing:
            continue
        _write(con, pattern)
    con.commit()
    n = con.execute("SELECT COUNT(*) AS c FROM crime_patterns").fetchone()["c"]
    con.close()
    return int(n)


def save_pattern(pattern: CrimePatternDNA) -> None:
    init_schema()
    con = connect()
    _write(con, pattern)
    con.commit()
    con.close()


def _write(con, pattern: CrimePatternDNA) -> None:
    upsert(con, "crime_patterns", "pattern_id", {
        "pattern_id": pattern.pattern_id,
        "version": pattern.version,
        "name": pattern.name,
        "description": pattern.description,
        "entry_signals": json.dumps(pattern.entry_signals),
        "movement_signals": json.dumps(pattern.movement_signals),
        "relationship_signals": json.dumps(pattern.relationship_signals),
        "geography_signals": json.dumps(pattern.geography_signals),
        "timing_signals": json.dumps(pattern.timing_signals),
        "exit_signals": json.dumps(pattern.exit_signals),
        "graph_signature": pattern.graph_signature,
        "temporal_signature": pattern.temporal_signature,
        "corridor_signature": pattern.corridor_signature,
        "created_at": utc_now(),
        "created_by": pattern.created_by,
        "active": 1 if pattern.active else 0,
        "confirmed_cases": pattern.confirmed_cases,
        "institutional_scope": pattern.institutional_scope,
    })


def list_patterns() -> list[CrimePatternDNA]:
    seed_library()
    con = connect()
    rows = [dict(r) for r in con.execute("SELECT * FROM crime_patterns ORDER BY pattern_id")]
    con.close()
    return [_row_to_pattern(r) for r in rows]


SIGNAL_AXES = (
    "entry_signals",
    "movement_signals",
    "relationship_signals",
    "geography_signals",
    "timing_signals",
    "exit_signals",
)


def measured_library() -> list[dict]:
    """Pattern DNA plus measured match counts and axis coverage."""
    patterns = list_patterns()
    init_schema()
    con = connect()
    try:
        stats_rows = con.execute(
            "SELECT pattern_id, COUNT(*) AS match_count, AVG(score) AS avg_score "
            "FROM pattern_matches GROUP BY pattern_id"
        ).fetchall()
    except Exception:
        stats_rows = []
    con.close()
    stats = {r["pattern_id"]: dict(r) for r in stats_rows}
    out = []
    for pattern in patterns:
        dump = pattern.model_dump()
        st = stats.get(pattern.pattern_id) or {}
        axes = []
        for axis in SIGNAL_AXES:
            signals = getattr(pattern, axis) or []
            axes.append({
                "axis": axis.replace("_signals", ""),
                "count": len(signals),
                "signals": signals,
                "coverage": round(100.0 * (len(signals) / 6.0), 1),
            })
        dump["axes"] = axes
        dump["signal_count"] = len(pattern.all_signals())
        dump["match_count"] = int(st.get("match_count") or 0)
        avg = st.get("avg_score")
        dump["avg_match_score"] = round(float(avg), 3) if avg is not None else None
        dump["measurable"] = True
        out.append(dump)
    return out


def library_snapshot() -> dict:
    """Compact Pattern DNA stats for the Command Center."""
    lib = measured_library()
    strengths = [p["avg_match_score"] for p in lib if p.get("avg_match_score") is not None]
    confirmed = sum(1 for p in lib if int(p.get("confirmed_cases") or 0) > 0)
    return {
        "confirmed_patterns": confirmed,
        "pattern_matches": sum(int(p.get("match_count") or 0) for p in lib),
        "average_match_strength": round(100.0 * sum(strengths) / len(strengths), 1) if strengths else None,
        "library_size": len(lib),
    }


def increment_confirmed(pattern_id: str) -> None:
    con = connect()
    con.execute(
        "UPDATE crime_patterns SET confirmed_cases = COALESCE(confirmed_cases,0)+1 WHERE pattern_id=?",
        (pattern_id,),
    )
    con.commit()
    con.close()
