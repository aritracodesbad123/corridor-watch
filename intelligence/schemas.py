"""Privacy-preserving intelligence records. Synthetic identifiers only."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IntelligenceSignal(BaseModel):
    intelligence_id: str
    source_institution: str
    entity_type: str = "ACCOUNT"
    entity_reference: str
    signal_type: str
    confidence: float = Field(ge=0, le=1)
    pattern_id: str = ""
    sharing_tier: Literal["LOCAL_ONLY", "SHARED_SIGNAL", "SHARED_PATTERN", "SHARED_ENTITY_RISK"] = "SHARED_SIGNAL"
    visibility: str = "external"
    timestamp: str = ""
    notes: str = ""

    def public_dict(self) -> dict:
        return self.model_dump()
