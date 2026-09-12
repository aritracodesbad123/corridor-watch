"""Crime Pattern DNA — reusable investigation fingerprints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CrimePatternDNA(BaseModel):
    pattern_id: str
    version: int = 1
    name: str
    description: str = ""
    entry_signals: list[str] = Field(default_factory=list)
    movement_signals: list[str] = Field(default_factory=list)
    relationship_signals: list[str] = Field(default_factory=list)
    geography_signals: list[str] = Field(default_factory=list)
    timing_signals: list[str] = Field(default_factory=list)
    exit_signals: list[str] = Field(default_factory=list)
    graph_signature: str = ""
    temporal_signature: str = ""
    corridor_signature: str = ""
    created_by: str = "system"
    active: bool = True
    confirmed_cases: int = 0

    def all_signals(self) -> set[str]:
        return set(
            self.entry_signals
            + self.movement_signals
            + self.relationship_signals
            + self.geography_signals
            + self.timing_signals
            + self.exit_signals
        )


SEED_PATTERNS = [
    CrimePatternDNA(
        pattern_id="CW-001",
        name="rapid_mule_fanout",
        description="New mule receives burst inflows and forwards almost all funds across a border.",
        entry_signals=["new_account", "incoming_spike"],
        movement_signals=["rapid_fanout", "high_pass_through"],
        relationship_signals=["shared_device"],
        geography_signals=["cross_border"],
        timing_signals=["short_hold_period"],
        exit_signals=["shared_beneficiary"],
        graph_signature="fan_in>=4;pass_through>=0.9",
        temporal_signature="hold_minutes<180",
        corridor_signature="cross_border",
    ),
    CrimePatternDNA(
        pattern_id="CW-002",
        name="split_feed_sink",
        description="Many sub-threshold feeders converge on one sink then exit.",
        entry_signals=["incoming_spike"],
        movement_signals=["structuring", "fan_in"],
        relationship_signals=["shared_beneficiary"],
        geography_signals=["cross_border"],
        timing_signals=["burst_window"],
        exit_signals=["overseas_exit"],
        graph_signature="fan_in>=6",
        temporal_signature="burst_hours<=24",
        corridor_signature="multi_feeder",
    ),
    CrimePatternDNA(
        pattern_id="CW-003",
        name="shared_device_ring",
        description="Unrelated accounts operate from the same hardware fingerprint.",
        entry_signals=["new_account"],
        movement_signals=["burst_send"],
        relationship_signals=["shared_device"],
        geography_signals=["cross_border"],
        timing_signals=["same_day_burst"],
        exit_signals=["external_beneficiary"],
        graph_signature="shared_device_groups>=1",
        temporal_signature="same_day",
        corridor_signature="any",
    ),
    CrimePatternDNA(
        pattern_id="CW-004",
        name="synthetic_identity_inflow",
        description="Young thin-file identity receives high-value inflows inconsistent with profile.",
        entry_signals=["young_account", "new_device"],
        movement_signals=["abnormal_velocity"],
        relationship_signals=["relationship_reuse"],
        geography_signals=["unknown_origin"],
        timing_signals=["short_account_life"],
        exit_signals=[],
        graph_signature="account_age<=7",
        temporal_signature="age_days<=7",
        corridor_signature="??->*",
    ),
    CrimePatternDNA(
        pattern_id="CW-005",
        name="multi_hop_layering",
        description="Funds layered through 3+ owned intermediates before overseas exit.",
        entry_signals=["incoming_spike"],
        movement_signals=["multi_hop", "rapid_movement"],
        relationship_signals=["owned_intermediates"],
        geography_signals=["cross_institution", "cross_border"],
        timing_signals=["short_hold_period"],
        exit_signals=["overseas_exit"],
        graph_signature="hop_count>=3",
        temporal_signature="hours<=24",
        corridor_signature="multi_country",
    ),
    CrimePatternDNA(
        pattern_id="CW-006",
        name="cross_institution_rail",
        description="Bank to bank to payment provider to overseas collector.",
        entry_signals=["new_account"],
        movement_signals=["cross_institution"],
        relationship_signals=["payment_provider"],
        geography_signals=["cross_border"],
        timing_signals=["short_hold_period"],
        exit_signals=["overseas_exit"],
        graph_signature="institution_count>=3",
        temporal_signature="hours<=12",
        corridor_signature="provider_exit",
    ),
]
