"""Synthetic intelligence provider. Replace later with an authorized feed."""
from __future__ import annotations

from intelligence.repository import save_signal
from intelligence.schemas import IntelligenceSignal
from pubsub.schemas import utc_now

MIDDLE_BANK_SIGNAL = IntelligenceSignal(
    intelligence_id="INT-00421",
    source_institution="BANK_PH",
    entity_type="ACCOUNT",
    entity_reference="EXT-MID-HK-D",
    signal_type="confirmed_mule",
    confidence=0.91,
    pattern_id="CW-007",
    sharing_tier="SHARED_ENTITY_RISK",
    visibility="external",
    notes="Synthetic hashed reference only. No customer name or raw ledger row.",
)


def simulate_resolution(*, actor: str = "system") -> dict:
    """Reveal one previously unknown downstream hop. Deterministic."""
    signal = MIDDLE_BANK_SIGNAL.model_copy()
    signal.timestamp = utc_now()
    save_signal(signal, actor=actor)
    return {
        "applied": True,
        "signal": signal.public_dict(),
        "resolved_boundary": "UNK-DOWNSTREAM",
        "now_visible_as": signal.entity_reference,
        "note": "External intelligence, not an observed home-bank fact.",
    }


def ingest_signal(payload: dict, *, actor: str) -> dict:
    signal = IntelligenceSignal.model_validate(payload)
    save_signal(signal, actor=actor)
    return signal.public_dict()

