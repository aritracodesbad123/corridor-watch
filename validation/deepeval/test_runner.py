import deepeval

from investigations.service import build_investigation
from pubsub.ingestion import ingest_transaction
from validation.datasets.golden import cases as golden_cases
from validation.deepeval.runner import run_offline
from validation.reliability.test_idempotency import _event


def test_deepeval_package_imports():
    assert deepeval.__version__


def test_deepeval_offline_runner_writes_artifact(isolated_db):
    cases = []
    for row in golden_cases():
        txn_id = row["txn_id"]
        ingest_transaction(
            _event(
                txn_id=txn_id,
                source_event_id=row.get("source_event_id") or f"E-{txn_id}",
                amount=row["amount"],
                account_age_days=row["account_age_days"],
            ),
            message_id=f"m-{txn_id}",
        )
        result = build_investigation(txn_id, use_gemini=False)
        report = result["report"]
        allowed = [e["evidence_id"] for e in result["evidence"]]
        claimed = [e["evidence_id"] for e in (report.get("supporting_evidence") or [])]
        cases.append({
            "input": txn_id,
            "actual_output": report.get("recommended_disposition") or "",
            "expected_output": row["expected_disposition"],
            "additional_metadata": {
                "claim_ids": claimed,
                "allowed_ids": allowed,
                "present_ids": allowed,
                "verdicts": [report.get("recommended_disposition"), report.get("recommended_disposition")],
                "retrieval_context": [e.get("description") or e.get("evidence_id") for e in result["evidence"]],
            },
        })
    payload = run_offline(cases)
    assert payload["ran"] is True
    assert payload["case_count"] >= 100
    assert payload["cases"][0]["scores"]["EvidenceGroundingMetric"]["score"] is not None
    if payload.get("official_metrics") == "RAN":
        assert "faithfulness" in payload
    else:
        assert payload.get("official_metrics") == "NOT_MEASURED"
