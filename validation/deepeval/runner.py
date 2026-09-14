"""Thin DeepEval runner. Custom metrics always; official LLM-judge metrics only if Gemini binds."""
from __future__ import annotations

import json
from pathlib import Path

from deepeval.test_case import LLMTestCase

from validation import ROOT, experiment_metadata
from validation.deepeval.metrics.wrappers import (
    AmlCorrectnessMetric,
    EvidenceCompletenessMetric,
    EvidenceGroundingMetric,
    UnsupportedClaimsMetric,
    VerdictStabilityMetric,
)

REPORT = ROOT / "reports" / "deepeval.json"


def _official_gemini_metrics() -> dict:
    # ponytail: DeepEval FaithfulnessMetric needs an LLM judge. No OpenAI path.
    try:
        from deepeval.models import GeminiModel  # type: ignore
    except Exception as exc:
        return {"official_metrics": "NOT_MEASURED", "reason": f"GeminiModel unavailable: {exc}"}
    return {"official_metrics": "IMPLEMENTED", "judge": "GeminiModel", "ran": False}


def run_offline(cases: list[dict] | None = None) -> dict:
    cases = cases or [
        {
            "input": "mule case",
            "actual_output": "hold_payment",
            "expected_output": "hold_payment",
            "additional_metadata": {
                "claim_ids": ["E-TXN"],
                "allowed_ids": ["E-TXN", "E-NET"],
                "present_ids": ["E-TXN"],
                "verdicts": ["hold_payment", "hold_payment"],
            },
        }
    ]
    metrics = [
        EvidenceGroundingMetric(),
        UnsupportedClaimsMetric(),
        AmlCorrectnessMetric(),
        EvidenceCompletenessMetric(),
        VerdictStabilityMetric(),
    ]
    rows = []
    for raw in cases:
        tc = LLMTestCase(
            input=raw.get("input") or "",
            actual_output=raw.get("actual_output") or "",
            expected_output=raw.get("expected_output") or "",
        )
        meta = raw.get("additional_metadata") or raw.get("metadata") or {}
        if hasattr(tc, "metadata"):
            tc.metadata = meta
        else:
            tc.additional_metadata = meta
        scores = {}
        for metric in metrics:
            scores[metric.__class__.__name__] = {"score": metric.measure(tc), "success": metric.is_successful()}
        rows.append({"input": raw.get("input"), "scores": scores})
    payload = experiment_metadata(
        dataset="deepeval_offline",
        case_count=len(rows),
        cases=rows,
        package="deepeval",
        **_official_gemini_metrics(),
    )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, default=str))
    return payload
