"""Thin DeepEval runner. Custom metrics always; official LLM-judge metrics only if Gemini binds."""
from __future__ import annotations

import json
import os
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


def _official_gemini_metrics(cases: list[dict]) -> dict:
    if os.getenv("CW_GEMINI_LIVE") != "1":
        return {"official_metrics": "NOT_MEASURED", "reason": "CW_GEMINI_LIVE unset"}
    try:
        from deepeval.metrics import FaithfulnessMetric
        from deepeval.models import GeminiModel
    except Exception as exc:
        return {"official_metrics": "NOT_MEASURED", "reason": f"judge import failed: {exc}"}
    try:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        model = GeminiModel(
            model=os.getenv("GEMINI_MODEL") or "gemini-2.5-flash",
            api_key=api_key,
            project=os.getenv("GOOGLE_CLOUD_PROJECT") or "corridor-watch-508420",
            location=os.getenv("VERTEX_LOCATION") or "global",
            use_vertexai=True if not api_key or os.getenv("GEMINI_BACKEND") == "vertex" else None,
        )
        metric = FaithfulnessMetric(model=model, threshold=0.7, async_mode=False)
        sample = cases[:10]
        scores = []
        for raw in sample:
            meta = raw.get("additional_metadata") or raw.get("metadata") or {}
            ctx = meta.get("retrieval_context") or [raw.get("expected_output") or ""]
            tc = LLMTestCase(
                input=raw.get("input") or "",
                actual_output=raw.get("actual_output") or "",
                retrieval_context=[str(c) for c in ctx if c],
            )
            scores.append(float(metric.measure(tc)))
        mean = round(sum(scores) / len(scores), 4) if scores else None
        return {
            "official_metrics": "RAN",
            "judge": "FaithfulnessMetric/GeminiModel",
            "official_n": len(scores),
            "faithfulness": mean,
        }
    except Exception as exc:
        return {"official_metrics": "NOT_MEASURED", "reason": str(exc)}


def run_offline(cases: list[dict] | None = None) -> dict:
    cases = list(cases or [])
    ran = len(cases) >= 100
    if not cases:
        cases = [{
            "input": "mule case",
            "actual_output": "hold_payment",
            "expected_output": "hold_payment",
            "additional_metadata": {
                "claim_ids": ["E-TXN"],
                "allowed_ids": ["E-TXN", "E-NET"],
                "present_ids": ["E-TXN"],
                "verdicts": ["hold_payment", "hold_payment"],
            },
        }]
        ran = False
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
    means = {}
    for name in rows[0]["scores"]:
        vals = [r["scores"][name]["score"] for r in rows]
        means[name] = round(sum(vals) / len(vals), 4)
    payload = experiment_metadata(
        dataset="deepeval_offline",
        case_count=len(rows),
        cases=rows,
        package="deepeval",
        ran=ran,
        mean_scores=means,
        **_official_gemini_metrics(cases),
    )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, default=str))
    return payload
