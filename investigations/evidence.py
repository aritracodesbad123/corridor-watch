"""Common evidence representation with stable IDs."""
from __future__ import annotations

import hashlib
import json

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
    try:
        from multimodal_sof import latest_verification
        doc = latest_verification(txn.get("txn_id") or "")
        if doc:
            items.append(EvidenceItem(
                evidence_id="E-DOC",
                type="document_verification",
                description=(
                    f"Source-of-funds document {doc.get('verification_status')}: "
                    f"{doc.get('verification_note')}"
                ),
                source="document_verifier",
                source_ref=str(doc.get("filename") or txn.get("txn_id") or ""),
                confidence=0.9 if doc.get("verification_status") == "VERIFIED_MATCH" else 0.45,
            ))
    except Exception:
        pass
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
        from graph_features import business_context
        items.append(EvidenceItem(
            evidence_id="E-RISK",
            type="account_risk",
            description=(
                f"Account graph risk {risk.get('risk_score')} pattern {risk.get('primary_pattern')} "
                f"context={business_context(risk)} "
                f"age={risk.get('account_age_days')}d pass-through={risk.get('pass_through_ratio')} "
                f"hold={risk.get('avg_hold_time_minutes')}m"
            ),
            source="graph_feature",
            source_ref=str(risk.get("account_id") or ""),
        ))
    visibility = (network or {}).get("visibility") or {}
    if visibility:
        items.append(EvidenceItem(
            evidence_id="E-VIS",
            type="network_visibility",
            description=(
                f"Network visibility {visibility.get('network_visibility_pct')}% "
                f"(observed {visibility.get('observed', {}).get('nodes', 0)} nodes; "
                f"unknown boundaries {visibility.get('unknown', {}).get('boundaries', 0)}). "
                "This is coverage, not guilt."
            ),
            source="visibility",
            source_ref=(network or {}).get("network_id") or "",
            confidence=float(visibility.get("network_visibility_score") or 0),
        ))
    for boundary in ((network or {}).get("boundaries") or [])[:6]:
        items.append(EvidenceItem(
            evidence_id=boundary.get("boundary_id") or "BOUNDARY-00",
            type="institutional_boundary",
            description=boundary.get("description") or "Institutional boundary",
            source="visibility",
            source_ref=boundary.get("account_id") or "",
            confidence=0.4,
        ))
    try:
        from intelligence.repository import list_signals
        for sig in list_signals(20)[:4]:
            items.append(EvidenceItem(
                evidence_id=sig.get("intelligence_id") or "EXT-00",
                type="external_intelligence",
                description=(
                    f"{sig.get('signal_type')} from {sig.get('source_institution')} "
                    f"on {sig.get('entity_reference')} (synthetic reference only)"
                ),
                source="external_intelligence",
                source_ref=sig.get("entity_reference") or "",
                confidence=float(sig.get("confidence") or 0.5),
            ))
    except Exception:
        pass
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
    from risk.tiers import RiskTier, assign_tier
    tier = assign_tier(score)
    if tier is RiskTier.CRITICAL:
        disposition = "escalate_fiu"
    elif tier is RiskTier.HIGH:
        disposition = "hold_payment"
    elif tier is RiskTier.MEDIUM:
        disposition = "monitor"
    else:
        disposition = "clear"
    confidence = _confidence_for_case(score, evidence, matches, network, risk)
    pattern_names = [m["pattern_id"] for m in matches]
    alts = [
        "This could be ordinary family support money around payday or a festival.",
        "This could be a real business moving cash between related companies that share staff and phones.",
    ]
    if not matches:
        alts.append("We have not yet matched this to a known Crime Pattern DNA case — treat the story as provisional.")
    vis = (network or {}).get("visibility") or {}
    next_checks = [
        "Pull opening documents and confirm who really owns the account that looks like a temporary holding point.",
        "Ask for invoices or source-of-funds papers and check whether the amounts match stated income or trade.",
        "Ask the sending bank whether this phone or beneficiary is already on a watch or block list.",
    ]
    if vis.get("unknown", {}).get("boundaries"):
        next_checks.append("Ask for authorized external intel on the hops we cannot see yet (downstream / upstream gaps).")
    unknown_areas = [
        f"{b.get('boundary_id')}: {b.get('description')}"
        for b in ((network or {}).get("boundaries") or [])
        if b.get("visibility") in {"unknown", "external"}
    ][:8]
    ext_ids = [e.evidence_id for e in evidence if str(e.evidence_id).startswith("INT-") or str(e.evidence_id).startswith("EXT-")]
    txn_count = ((network or {}).get("features") or {}).get("txn_count", 0)
    dna_bit = (
        f"Closest known pattern match is {matches[0]['name']} ({matches[0]['pattern_id']})."
        if matches else "No strong match to a known Crime Pattern DNA case yet."
    )
    summary = (
        f"Payment {txn.get('txn_id')} sits in a cluster of about {txn_count} related transfers on corridor {txn.get('corridor')}. "
        f"{dna_bit} "
        f"Automated score is {score:.0f}. "
        f"Recommended human step: {disposition.replace('_', ' ')}"
    )
    source = (risk or {}).get("risk_source") or "model"
    screen = (risk or {}).get("screen_score")
    graph_only = (risk or {}).get("graph_score")
    extra = ""
    if graph_only is not None and screen is not None:
        extra = f" Network score {float(graph_only):.0f}; screening score {float(screen):.0f}."
    primary = (risk or {}).get("primary_pattern") or txn.get("primary_pattern") or "elevated_activity"
    hypothesis = (
        f"Working theory: the money movement looks like '{str(primary).replace('_', ' ')}' "
        f"with overall risk {score:.0f} (source: {source}).{extra} "
        "A human still confirms purpose before any freeze."
    )
    contradicting = []
    if score < 50:
        contradicting.append(EvidenceItem(
            evidence_id="E-LOW",
            type="score",
            description="Overall risk is below the high bar; ordinary corridor traffic is still plausible.",
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
            f"We are about {confidence}% confident based on how much of the network we can see and how many evidence items we have. "
            "This write-up is rule-based unless Gemini later rewrites it in plain English."
        ),
        model_version="deterministic-v1",
        model_provider="none",
        prompt_version="investigator-v8",
        evidence_hash=hashlib.sha256(
            json.dumps([e.model_dump() for e in evidence], sort_keys=True, default=str).encode()
        ).hexdigest()[:16],
        output_hash=hashlib.sha256(
            f"{hypothesis}|{disposition}|{confidence}".encode()
        ).hexdigest()[:16],
        pattern_versions=[f"{m['pattern_id']}@v{m.get('version', 1)}" for m in matches],
        gemini_used=False,
        grounded=True,
        network_visibility_score=vis.get("network_visibility_score"),
        unknown_areas=unknown_areas,
        visibility_counts={
            "observed": vis.get("observed") or {},
            "external": vis.get("external") or {},
            "inferred": vis.get("inferred") or {},
            "unknown": vis.get("unknown") or {},
        },
        external_intelligence_ids=ext_ids,
    )
