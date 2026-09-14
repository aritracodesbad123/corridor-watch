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
        EvidenceItem(evidence_id="E-TXN", type="txn", description="seed amount 400", source="ledger"),
    ])
    invented = _report(
        supporting_evidence=[
            EvidenceItem(evidence_id="E-FAKE", type="txn", description="invented node BANK-Z", source="model"),
            EvidenceItem(evidence_id="E-TXN", type="txn", description="amount 999999 at BANK-Z", source="ledger"),
        ],
        recommended_disposition="freeze_account",
    )
    pre_ids = [e.evidence_id for e in invented.supporting_evidence]
    pre_text = " ".join(e.description or "" for e in invented.supporting_evidence)
    pre_unsupported = unsupported_claims(pre_ids, allowed)
    gated = apply_grounding_gate(invented, allowed, det, [])
    gated_ids = [e.evidence_id for e in (gated.supporting_evidence or [])]
    post_unsupported = unsupported_claims(gated_ids, allowed)
    gated_text = " ".join(e.description or "" for e in (gated.supporting_evidence or []))
    entity_present_pre = "BANK-Z" in pre_text
    numerical_present_pre = "999999" in pre_text
    entity_trap_caught = entity_present_pre and "BANK-Z" not in gated_text
    numerical_trap_caught = numerical_present_pre and "999999" not in gated_text
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
        "hallucination_rate": 0.0 if entity_trap_caught and numerical_trap_caught else 1.0,
        "unsupported_claim_rate": post_unsupported,
        "unsupported_claim_rate_pre_gate": pre_unsupported,
        "entity_error_rate": 0.0 if entity_trap_caught else 1.0,
        "numerical_error_rate": 0.0 if numerical_trap_caught else 1.0,
        "material_error_rate": 1.0 if "E-FAKE" in gated_ids else 0.0,
        "numerical_trap_caught": numerical_trap_caught,
        "entity_trap_caught": entity_trap_caught,
        "gate_rejected_invented_ids": "E-FAKE" not in gated_ids,
        "live_ungrounded_rate": live_rate,
        "live_n": live_n,
        "note": "Split: hallucination=invented material that survived the gate; unsupported=IDs not in allowed after gate; entity/numerical traps are gate catches.",
    }
    REPORT.write_text(json.dumps(payload, indent=2))
    assert payload["gate_rejected_invented_ids"]
    assert entity_trap_caught
    assert numerical_trap_caught
    assert post_unsupported <= 0.05
    assert pre_unsupported == 0.5
    assert unsupported_claims(["E-TXN"], allowed) <= 0.05
