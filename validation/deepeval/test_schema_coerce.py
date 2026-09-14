from investigations.schemas import EvidenceItem, InvestigationReport
from agent import _parse_grounded_json


def _fallback() -> InvestigationReport:
    return InvestigationReport(
        investigation_summary="det summary",
        risk_hypothesis="det hyp",
        supporting_evidence=[EvidenceItem(evidence_id="E-TXN", type="txn", description="wire", source="ledger")],
        recommended_disposition="monitor",
        confidence=40,
        uncertainty="det",
    )


def test_sloppy_gemini_json_still_validates():
    fb = _fallback()
    raw = _parse_grounded_json(
        '{"investigation_summary":"' + ("x" * 2500) + '",'
        '"risk_hypothesis":"mule",'
        '"recommended_disposition":"HOLD",'
        '"confidence":80,'
        '"uncertainty":"' + ("u" * 1200) + '",'
        '"supporting_evidence":[{"evidence_id":"E-TXN","type":"txn","description":"ok","source":"ledger","confidence":80}],'
        '"matched_patterns":[{"pattern_id":"mule_pass_through"}],'
        '"alternative_explanations":"payroll",'
        '"recommended_next_checks":["call bank"]}',
        fb,
    )
    report = InvestigationReport.model_validate(raw)
    assert report.recommended_disposition == "hold_payment"
    assert report.confidence == 80
    assert len(report.investigation_summary) <= 2000
    assert len(report.uncertainty) <= 800
    assert report.supporting_evidence[0].confidence <= 1.0
    assert report.matched_patterns == ["mule_pass_through"]
    assert report.alternative_explanations == ["payroll"]
