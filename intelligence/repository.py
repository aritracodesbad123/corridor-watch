"""Durable store for synthetic intelligence signals."""
from __future__ import annotations

import json

from db import connect, init_schema, upsert
from intelligence.schemas import IntelligenceSignal
from pubsub.schemas import utc_now


def save_signal(signal: IntelligenceSignal, *, actor: str = "system") -> IntelligenceSignal:
    init_schema()
    if not signal.timestamp:
        signal.timestamp = utc_now()
    con = connect()
    upsert(con, "intelligence_signals", "intelligence_id", {
        "intelligence_id": signal.intelligence_id,
        "source_institution": signal.source_institution,
        "entity_type": signal.entity_type,
        "entity_reference": signal.entity_reference,
        "signal_type": signal.signal_type,
        "confidence": signal.confidence,
        "pattern_id": signal.pattern_id,
        "sharing_tier": signal.sharing_tier,
        "visibility": signal.visibility,
        "payload": json.dumps(signal.public_dict()),
        "created_at": signal.timestamp,
        "created_by": actor,
    })
    con.commit()
    con.close()
    return signal


def list_signals(limit: int = 80) -> list[dict]:
    init_schema()
    con = connect()
    try:
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM intelligence_signals ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()]
    except Exception:
        rows = []
    con.close()
    out = []
    for row in rows:
        try:
            out.append(json.loads(row.get("payload") or "{}") or _from_row(row))
        except json.JSONDecodeError:
            out.append(_from_row(row))
    return out


def referenced_entities() -> set[str]:
    return {s.get("entity_reference") for s in list_signals(200) if s.get("entity_reference")}


def _from_row(row: dict) -> dict:
    return {
        "intelligence_id": row.get("intelligence_id"),
        "source_institution": row.get("source_institution"),
        "entity_type": row.get("entity_type"),
        "entity_reference": row.get("entity_reference"),
        "signal_type": row.get("signal_type"),
        "confidence": row.get("confidence"),
        "pattern_id": row.get("pattern_id"),
        "sharing_tier": row.get("sharing_tier"),
        "visibility": row.get("visibility") or "external",
        "timestamp": row.get("created_at"),
    }
