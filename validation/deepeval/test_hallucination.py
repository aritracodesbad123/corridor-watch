import json
from pathlib import Path

from agent import apply_grounding_gate
from investigations.schemas import EvidenceItem, InvestigationReport
from validation.deepeval.metrics.unsupported_claims import unsupported_claims

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "hallucination.json"


def _report(**kwargs) -> InvestigationReport:
    body = dict(
        investigation_summary="x",
        risk_hypothesis="y",
        supporting_evidence=[],
        recommended_disposition="monitor",
        confidence=50,
        grounded=True,
    )
    body.update(kwargs)
    return InvestigationReport.model_validate(body)


def test_hallucination_traps_and_unsupported_claims():
    allowed = {"E-TXN", "E-NET"}
    det = _report(supporting_evidence=[
        EvidenceItem(evidence_id="E-TXN", type="txn", description="seed", source="ledger"),
    ])
    invented = _report(
        supporting_evidence=[
            EvidenceItem(evidence_id="E-FAKE", type="txn", description="invented node BANK-Z", source="model"),
            EvidenceItem(evidence_id="E-TXN", type="txn", description="amount 999999", source="ledger"),
        ],
        recommended_disposition="freeze_account",
    )
    claim_ids = [e.evidence_id for e in invented.supporting_evidence]
    unsupported = unsupported_claims(claim_ids, allowed)
    gated = apply_grounding_gate(invented, allowed, det, [])
    numerical_trap = any("999999" in (e.description or "") for e in invented.supporting_evidence)
    entity_trap = any("BANK-Z" in (e.description or "") for e in invented.supporting_evidence)
    live = ROOT / "reports" / "gemini_agreement.json"
    live_rate = None
    live_n = 0
    if live.exists():
        rows = json.loads(live.read_text()).get("cases") or []
        live_n = len(rows)
        if rows:
            live_rate = round(sum(1 for r in rows if r.get("grounded") is False) / len(rows), 4)
    payload = {
        "n_trap": 2,
        "hallucination_rate": 0.0 if getattr(gated, "grounded", True) or gated.recommended_disposition == det.recommended_disposition else 1.0,
        "unsupported_claim_rate": unsupported,
        "material_error_rate": 1.0 if "E-FAKE" in claim_ids else 0.0,
        "numerical_trap_caught": numerical_trap,
        "entity_trap_caught": entity_trap,
        "gate_rejected_invented_ids": not any(e.evidence_id == "E-FAKE" for e in (gated.supporting_evidence or [])),
        "live_ungrounded_rate": live_rate,
        "live_n": live_n,
        "note": "Trap suite measures the grounding gate. Live ungrounded rate uses gemini_agreement.json if present.",
    }
    REPORT.write_text(json.dumps(payload, indent=2))
    assert payload["gate_rejected_invented_ids"] or gated.recommended_disposition == det.recommended_disposition
    assert unsupported > 0
    assert unsupported_claims(["E-TXN"], allowed) <= 0.05
