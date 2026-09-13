"""Structured investigation artefacts. Gemini must return this shape."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    evidence_id: str
    type: str
    description: str
    source: str
    source_ref: str = ""
    confidence: float = Field(default=1.0, ge=0, le=1)


class InvestigationReport(BaseModel):
    investigation_summary: str = Field(min_length=1, max_length=2000)
    risk_hypothesis: str = Field(min_length=1, max_length=1200)
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=20)
    contradicting_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=12)
    matched_patterns: list[str] = Field(default_factory=list, max_length=12)
    alternative_explanations: list[str] = Field(default_factory=list, max_length=8)
    recommended_next_checks: list[str] = Field(default_factory=list, max_length=10)
    recommended_disposition: Literal["clear", "monitor", "hold_payment", "escalate_fiu", "freeze_account"] = "monitor"
    confidence: int = Field(ge=0, le=100)
    uncertainty: str = Field(default="", max_length=800)
    model_version: str = ""
    model_provider: str = ""
    prompt_version: str = ""
    evidence_hash: str = ""
    input_hash: str = ""
    output_hash: str = ""
    pattern_versions: list[str] = Field(default_factory=list)
    gemini_used: bool = False
    grounded: bool = True
    network_visibility_score: float | None = Field(default=None, ge=0, le=1)
    unknown_areas: list[str] = Field(default_factory=list, max_length=12)
    visibility_counts: dict = Field(default_factory=dict)
    external_intelligence_ids: list[str] = Field(default_factory=list, max_length=12)
