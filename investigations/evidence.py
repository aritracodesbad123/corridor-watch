"""Common evidence representation with stable IDs."""
from __future__ import annotations

from investigations.schemas import EvidenceItem, InvestigationReport


def build_evidence_items(txn: dict, network: dict, risk: dict | None, matches: list[dict]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    items.append(EvidenceItem(
        evidence_id="E-TXN",
        type="transaction",
        description=(
            f"Transaction {txn.get('txn_id')} {txn.get('amount')} {txn.get('currency') or 'USD'} "
            f"on corridor {txn.get('corridor')} from {txn.get('sender_id')} to {txn.get('receiver_id')}"
        ),
        source="ledger",
        source_ref=txn.get("txn_id") or "",
    ))
    features = (network or {}).get("features") or {}
    if features:
        items.append(EvidenceItem(
            evidence_id="E-NET",
            type="network_size",
            description=(
                f"Bounded network has {features.get('account_count', 0)} accounts and "
                f"{features.get('txn_count', 0)} transactions "
                f"({features.get('institution_count', 0)} institutions)"
            ),
            source="graph_feature",
            source_ref=(network or {}).get("network_id") or "",
        ))
    if features.get("shared_device_groups"):
        items.append(EvidenceItem(
            evidence_id="E-DEV",
            type="shared_device",
            description=f"{features['shared_device_groups']} shared-device group(s) in the bounded neighborhood",
            source="graph_feature",
            source_ref="shared_device_groups",
        ))
    if features.get("shared_beneficiary_groups"):
        items.append(EvidenceItem(
            evidence_id="E-BEN",
            type="shared_beneficiary",
            description=f"{features['shared_beneficiary_groups']} shared-beneficiary group(s) observed",
            source="graph_feature",
            source_ref="shared_beneficiary_groups",
        ))
    if risk:
        items.append(EvidenceItem(
            evidence_id="E-RISK",
            type="account_risk",
            description=(
                f"Account graph risk {risk.get('risk_score')} pattern {risk.get('primary_pattern')} "
                f"age={risk.get('account_age_days')}d pass-through={risk.get('pass_through_ratio')} "
                f"hold={risk.get('avg_hold_time_minutes')}m"
            ),
            source="graph_feature",
            source_ref=str(risk.get("account_id") or ""),
        ))
    for match in matches[:5]:
        items.append(EvidenceItem(
            evidence_id=f"E-{match['pattern_id']}",
            type="pattern_match",
            description=f"Crime Pattern DNA {match['pattern_id']} ({match['name']}) score {match['score']}",
            source="crime_pattern_dna",
            source_ref=match["pattern_id"],
            confidence=min(1.0, float(match["score"])),
        ))
    return items


def resolve_investigation_risk(txn_id: str, txn: dict, stored_risk: dict | None) -> dict:
    """Prefer stored graph scores; otherwise score the live neighborhood.

    Live-stream accounts have no risk_scores row, so falling back to the ingest
    cheap-screen made almost every campaign case look like 63.
    """
    stored = dict(stored_risk or {})
    usable = stored.get("fan_in_count") is not None or stored.get("pass_through_ratio") is not None
    if usable and stored.get("risk_score") not in (None, ""):
        return {**stored, "risk_source": "risk_scores", "screen_score": txn.get("risk_score")}
    try:
        from counterfactual import features_for_case
        from graph_features import composite_score, pattern_scores
        feats = features_for_case(txn_id)
        patterns = pattern_scores(feats, txn)
        graph_score, primary = composite_score(feats, patterns)
        screen = float(txn.get("risk_score") or 0)
        fused = round(min(100.0, 0.7 * graph_score + 0.3 * screen), 1)
        return {
            **feats,
            "risk_score": fused,
            "graph_score": graph_score,
            "screen_score": screen,
            "primary_pattern": primary or txn.get("primary_pattern") or "elevated_activity",
            "risk_source": "live_neighborhood",
        }
    except Exception:
        if stored:
            return {**stored, "risk_source": "risk_scores"}
        return {
            "risk_score": float(txn.get("risk_score") or 0),
            "risk_source": "screen_only",
            "screen_score": txn.get("risk_score"),
        }


def _confidence_for_case(
    score: float,
    evidence: list[EvidenceItem],
    matches: list[dict],
    network: dict,
    risk: dict | None,
) -> int:
    """Case-specific confidence — not a 4-bucket constant."""
    conf = 36 + min(38, float(score) * 0.4)
    ev_n = len(evidence or [])
    conf += min(10, ev_n * 1.4)
    if ev_n <= 1:
        conf -= 12
    features = ((network or {}).get("features") or {})
    txn_count = int(features.get("txn_count") or 0)
    if txn_count <= 1:
        conf -= 11
    elif txn_count >= 6:
        conf += 6
    if matches:
        top = max(float(m.get("score") or 0) for m in matches)
        conf += min(12, top * 14)
    else:
        conf -= 7
    risk = risk or {}
    try:
        if float(risk.get("pass_through_ratio") or 0) >= 0.9:
            conf += 4
    except (TypeError, ValueError):
        pass
    try:
        if risk.get("account_age_days") is not None and int(risk["account_age_days"]) <= 7:
            conf += 3
    except (TypeError, ValueError):
        pass
    doc = next((e for e in (evidence or []) if getattr(e, "evidence_id", "") == "E-DOC"), None)
    if doc:
        text = getattr(doc, "description", "") or ""
        if "VERIFIED_MATCH" in text:
            conf += 5
        elif "AMOUNT_DISCREPANCY" in text or "UNVERIFIED" in text:
            conf += 4
    if (risk or {}).get("risk_source") == "screen_only":
        conf -= 8
    return int(max(28, min(93, round(conf))))


def deterministic_report(
    txn: dict,
    evidence: list[EvidenceItem],
    matches: list[dict],
    risk: dict | None,
    network: dict,
) -> InvestigationReport:
    score = float((risk or {}).get("risk_score") or txn.get("risk_score") or 0)
    if score >= 75:
        disposition = "escalate_fiu"
    elif score >= 50:
        disposition = "hold_payment"
    elif score >= 40:
        disposition = "monitor"
    else:
        disposition = "clear"
    confidence = _confidence_for_case(score, evidence, matches, network, risk)
    pattern_names = [m["pattern_id"] for m in matches]
    alts = [
        "Legitimate family remittance clustered around a payroll or festival window.",
        "SME treasury movements across affiliates that share operations staff and devices.",
    ]
    if not matches:
        alts.append("Insufficient network overlap with known Crime Pattern DNA — treat hypothesis as provisional.")
    next_checks = [
        "Confirm account opening documents and beneficial ownership for the mule/sink candidate.",
        "Request source-of-funds artefacts and compare amounts to stated income.",
        "Ask the originating institution whether the shared device or beneficiary is already blocked.",
    ]
    summary = (
        f"Bounded network around {txn.get('txn_id')} contains {((network or {}).get('features') or {}).get('txn_count', 0)} "
        f"related transfers on {txn.get('corridor')}. "
        + (f"Closest DNA match is {matches[0]['pattern_id']} ({matches[0]['name']})." if matches else "No DNA match above threshold.")
    )
    source = (risk or {}).get("risk_source") or "model"
    screen = (risk or {}).get("screen_score")
    graph_only = (risk or {}).get("graph_score")
    extra = ""
    if graph_only is not None and screen is not None:
        extra = f" Neighborhood composite {float(graph_only):.0f}; ingest screen {float(screen):.0f}."
    hypothesis = (
        f"Primary hypothesis: {(risk or {}).get('primary_pattern') or txn.get('primary_pattern') or txn.get('fraud_scenario') or 'elevated_activity'} "
        f"behavior with graph risk {score:.0f} ({source}).{extra}"
    )
    contradicting = []
    if score < 50:
        contradicting.append(EvidenceItem(
            evidence_id="E-LOW",
            type="score",
            description="Composite risk is below the high-risk threshold; legitimate corridor activity remains plausible.",
            source="risk_fusion",
            source_ref="risk_score",
            confidence=0.6,
        ))
    return InvestigationReport(
        investigation_summary=summary,
        risk_hypothesis=hypothesis,
        supporting_evidence=evidence,
        contradicting_evidence=contradicting,
        matched_patterns=pattern_names,
        alternative_explanations=alts,
        recommended_next_checks=next_checks,
        recommended_disposition=disposition,  # type: ignore[arg-type]
        confidence=confidence,
        uncertainty=(
            f"Confidence {confidence} is scaled by neighborhood size, evidence count, and pattern overlap "
            f"(risk source: {(risk or {}).get('risk_source') or 'model'}). "
            "Deterministic synthesis only unless Gemini later rewrites this report."
        ),
        model_version="deterministic-v1",
        pattern_versions=[f"{m['pattern_id']}@v{m.get('version', 1)}" for m in matches],
        gemini_used=False,
        grounded=True,
    )
