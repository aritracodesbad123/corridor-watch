"""Correlated fraud campaign templates. Synthetic only."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CampaignSpec:
    scenario_id: str
    name: str
    ground_truth: str
    expected_signals: list[str]
    entities: list[str] = field(default_factory=list)


CAMPAIGNS = [
    CampaignSpec(
        scenario_id="CW-CAMP-MULE",
        name="mule_pass_through",
        ground_truth="fraud",
        expected_signals=["new_account", "rapid_movement", "short_hold", "cross_border"],
    ),
    CampaignSpec(
        scenario_id="CW-CAMP-FAN",
        name="fan_in_fan_out",
        ground_truth="fraud",
        expected_signals=["fan_in", "fan_out", "shared_beneficiary"],
    ),
    CampaignSpec(
        scenario_id="CW-CAMP-DEVICE",
        name="shared_device_ring",
        ground_truth="fraud",
        expected_signals=["shared_device", "unrelated_accounts"],
    ),
    CampaignSpec(
        scenario_id="CW-CAMP-BENE",
        name="shared_beneficiary_ring",
        ground_truth="fraud",
        expected_signals=["shared_beneficiary", "unrelated_accounts"],
    ),
    CampaignSpec(
        scenario_id="CW-CAMP-STRUCT",
        name="structuring",
        ground_truth="fraud",
        expected_signals=["split_outflow", "rapid_movement"],
    ),
    CampaignSpec(
        scenario_id="CW-CAMP-HOP",
        name="multi_hop_chain",
        ground_truth="fraud",
        expected_signals=["multi_hop", "cross_institution"],
    ),
    CampaignSpec(
        scenario_id="CW-CAMP-XINST",
        name="cross_institution_movement",
        ground_truth="fraud",
        expected_signals=["cross_institution", "payment_provider", "overseas_exit"],
    ),
    CampaignSpec(
        scenario_id="CW-CAMP-SYNTH",
        name="synthetic_identity",
        ground_truth="fraud",
        expected_signals=["young_account", "new_device", "abnormal_velocity"],
    ),
]
