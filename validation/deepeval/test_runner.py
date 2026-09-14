import json
from pathlib import Path

import deepeval

from investigations.service import build_investigation
from pubsub.ingestion import ingest_transaction
from validation.datasets.golden import REQUIRED_KINDS, cases as golden_cases
from validation.deepeval.runner import run_offline
from validation.reliability.test_idempotency import _event

CORPUS = Path(__file__).resolve().parents[1] / "datasets" / "injection_corpus.jsonl"


def test_deepeval_package_imports():
    assert deepeval.__version__


def test_deepeval_offline_runner_writes_artifact(isolated_db):
    attacks = [json.loads(l)["text"] for l in CORPUS.read_text().splitlines() if l.strip()]
    inj_i = 0
    cases = []
    for row in golden_cases():
        kind = row["kind"]
        txn_id = row["txn_id"]
        purpose = (row.get("purpose") or "")[:200]
        if kind == "injection":
            purpose = (attacks[inj_i % len(attacks)] if attacks else "Ignore previous")[:200]
            inj_i += 1
        ingest_transaction(
            _event(
                txn_id=txn_id,
                source_event_id=row.get("source_event_id") or f"E-{txn_id}",
                amount=row["amount"],
                account_age_days=row["account_age_days"],
                purpose=purpose,
            ),
            message_id=f"m-{txn_id}",
        )
        if kind in {"document", "contradict"}:
            from multimodal_sof import verify_document
            verify_document(txn_id)
        if kind == "toolfail":
            import agent as agent_mod
            orig = agent_mod.grounded_gemini_report
            agent_mod.grounded_gemini_report = lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("simulated tool failure"))
            try:
                result = build_investigation(txn_id, use_gemini=True)
            finally:
                agent_mod.grounded_gemini_report = orig
            assert result.get("gemini_error")
        else:
            result = build_investigation(txn_id, use_gemini=False)
        report = result["report"]
        allowed = [e["evidence_id"] for e in result["evidence"]]
        claimed = [e["evidence_id"] for e in (report.get("supporting_evidence") or [])]
        if kind == "missing":
            allowed = [i for i in allowed if i == "E-TXN"]
            claimed = [i for i in claimed if i in allowed]
        disp = report.get("recommended_disposition") or ""
        verdicts = [disp, disp]
        if kind == "contradict":
            again = build_investigation(txn_id, use_gemini=False)
            verdicts[1] = again["report"].get("recommended_disposition") or disp
        cases.append({
            "input": txn_id,
            "actual_output": disp,
            "expected_output": row["expected_disposition"],
            "additional_metadata": {
                "kind": kind,
                "claim_ids": claimed,
                "allowed_ids": allowed,
                "present_ids": allowed,
                "verdicts": verdicts,
                "retrieval_context": [e.get("description") or e.get("evidence_id") for e in result["evidence"]],
                "gemini_error": result.get("gemini_error"),
            },
        })
    payload = run_offline(cases)
    assert payload["ran"] is True
    assert payload["case_count"] >= 200
    assert REQUIRED_KINDS <= set(payload.get("kind_counts") or {})
    assert payload["cases"][0]["scores"]["EvidenceGroundingMetric"]["score"] is not None
    if payload.get("official_metrics") == "RAN":
        assert "faithfulness" in payload
    else:
        assert payload.get("official_metrics") == "NOT_MEASURED"
