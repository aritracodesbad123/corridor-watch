"""Extract Crime Pattern DNA from a human-confirmed investigation."""
from __future__ import annotations

import uuid

from patterns.matcher import observed_signals
from patterns.repository import increment_confirmed, list_patterns, save_pattern
from patterns.schema import CrimePatternDNA


CONFIRMING = {"hold_payment", "escalate_fiu", "freeze_account"}


def extract_from_confirmation(
    txn: dict,
    network: dict,
    risk: dict | None,
    decision: str,
    *,
    created_by: str,
) -> CrimePatternDNA | None:
    if decision not in CONFIRMING:
        return None
    signals = observed_signals(txn, network, risk)
    if not signals:
        return None

    # Strengthen the closest existing pattern when overlap is high.
    best = None
    best_score = 0.0
    for pattern in list_patterns():
        overlap = signals & pattern.all_signals()
        score = len(overlap) / max(len(pattern.all_signals()), 1)
        if score > best_score:
            best_score = score
            best = pattern
    if best and best_score >= 0.5:
        increment_confirmed(best.pattern_id)
        return best

    pattern = CrimePatternDNA(
        pattern_id=f"CW-{uuid.uuid4().hex[:4].upper()}",
        version=1,
        name=txn.get("primary_pattern") or txn.get("fraud_scenario") or "confirmed_network",
        description=f"Extracted from confirmed case {txn.get('txn_id')} by {created_by}",
        entry_signals=sorted(signals & {"new_account", "incoming_spike", "young_account", "new_device"}),
        movement_signals=sorted(signals & {"rapid_fanout", "high_pass_through", "structuring", "fan_in", "multi_hop", "rapid_movement", "cross_institution", "abnormal_velocity"}),
        relationship_signals=sorted(signals & {"shared_device", "shared_beneficiary", "owned_intermediates", "payment_provider"}),
        geography_signals=sorted(signals & {"cross_border", "unknown_origin", "cross_institution"}),
        timing_signals=sorted(signals & {"short_hold_period", "burst_window", "same_day_burst", "short_account_life"}),
        exit_signals=sorted(signals & {"shared_beneficiary", "overseas_exit", "external_beneficiary"}),
        graph_signature=f"txns={((network or {}).get('features') or {}).get('txn_count', 0)}",
        corridor_signature=txn.get("corridor") or "",
        created_by=created_by,
        confirmed_cases=1,
    )
    save_pattern(pattern)
    return pattern
