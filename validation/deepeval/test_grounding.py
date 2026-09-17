from investigations.schemas import EvidenceItem, InvestigationReport
from agent import apply_grounding_gate, ground_plain_text, ground_string_list
from validation.deepeval.metrics.evidence_grounding import evidence_grounding


def test_every_claim_must_cite_supplied_evidence():
    allowed = {"E-TXN"}
    fallback = InvestigationReport(
        investigation_summary="deterministic",
        risk_hypothesis="h",
        supporting_evidence=[EvidenceItem(evidence_id="E-TXN", type="transaction", description="wire", source="ledger")],
        recommended_disposition="monitor",
        confidence=40,
    )
    invented = InvestigationReport(
        investigation_summary="invented",
        risk_hypothesis="h",
        supporting_evidence=[EvidenceItem(evidence_id="E-FAKE", type="transaction", description="nope", source="model")],
        recommended_disposition="freeze_account",
        confidence=99,
    )
    out = apply_grounding_gate(invented, allowed, fallback, [])
    assert out.grounded is False
    assert evidence_grounding(["E-TXN"], allowed) == 1.0
    assert evidence_grounding(["E-FAKE"], allowed) == 0.0


def test_grounding_gate_does_not_let_gemini_downgrade():
    fallback = InvestigationReport(
        investigation_summary="deterministic",
        risk_hypothesis="h",
        supporting_evidence=[EvidenceItem(evidence_id="E-TXN", type="transaction", description="wire", source="ledger")],
        recommended_disposition="hold_payment",
        confidence=40,
    )
    milder = InvestigationReport(
        investigation_summary="gemini",
        risk_hypothesis="h",
        supporting_evidence=[EvidenceItem(evidence_id="E-TXN", type="transaction", description="wire", source="ledger")],
        recommended_disposition="monitor",
        confidence=40,
    )
    out = apply_grounding_gate(milder, {"E-TXN"}, fallback, [])
    assert out.grounded is True
    assert out.recommended_disposition == "hold_payment"
    assert getattr(out, "llm_raw_disposition", None) == "monitor"


def test_ground_plain_text_strips_invented_entities():
    allowed = "Payment TXN-123 scored 88 on corridor US-IN."
    text = "TXN-123 looks odd. Account ZZ-FAKE-999 is a mule with 12345 dollars."
    out, n = ground_plain_text(text, allowed)
    assert "ZZ-FAKE-999" not in out
    assert n >= 1
    cleaned, n2 = ground_string_list(
        ["TXN-123 is on the watch list.", "Invented BANK-XYZ-1 should vanish."],
        allowed,
    )
    assert any("TXN-123" in x for x in cleaned)
    assert all("BANK-XYZ-1" not in x for x in cleaned)
