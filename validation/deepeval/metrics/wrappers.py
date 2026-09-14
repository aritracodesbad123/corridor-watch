"""DeepEval BaseMetric adapters around the existing deterministic helpers."""
from __future__ import annotations

from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case import LLMTestCase

from validation.deepeval.metrics.aml_correctness import aml_correctness
from validation.deepeval.metrics.evidence_completeness import evidence_completeness
from validation.deepeval.metrics.evidence_grounding import evidence_grounding
from validation.deepeval.metrics.unsupported_claims import unsupported_claims
from validation.deepeval.metrics.verdict_stability import verdict_stability


def _meta(test_case: LLMTestCase) -> dict:
    return getattr(test_case, "metadata", None) or getattr(test_case, "additional_metadata", None) or {}


class _FnMetric(BaseMetric):
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold
        self.score = 0.0
        self.reason = ""
        self.success = False

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs):
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        return bool(self.success)


class EvidenceGroundingMetric(_FnMetric):
    def measure(self, test_case: LLMTestCase, *args, **kwargs):
        meta = _meta(test_case)
        self.score = evidence_grounding(meta.get("claim_ids") or [], set(meta.get("allowed_ids") or []))
        self.success = self.score >= self.threshold
        self.reason = f"grounded={self.score}"
        return self.score


class UnsupportedClaimsMetric(_FnMetric):
    def __init__(self, threshold: float = 0.05):
        super().__init__(threshold=threshold)

    def measure(self, test_case: LLMTestCase, *args, **kwargs):
        meta = _meta(test_case)
        self.score = 1.0 - unsupported_claims(meta.get("claim_ids") or [], set(meta.get("allowed_ids") or []))
        self.success = (1.0 - self.score) <= self.threshold
        self.reason = f"unsupported={1.0 - self.score}"
        return self.score


class AmlCorrectnessMetric(_FnMetric):
    def measure(self, test_case: LLMTestCase, *args, **kwargs):
        self.score = aml_correctness(test_case.actual_output or "", test_case.expected_output or "")
        self.success = self.score >= self.threshold
        self.reason = f"aml={self.score}"
        return self.score


class EvidenceCompletenessMetric(_FnMetric):
    def measure(self, test_case: LLMTestCase, *args, **kwargs):
        meta = _meta(test_case)
        self.score = evidence_completeness(set(meta.get("present_ids") or []))
        self.success = self.score >= self.threshold
        self.reason = f"complete={self.score}"
        return self.score


class VerdictStabilityMetric(_FnMetric):
    def measure(self, test_case: LLMTestCase, *args, **kwargs):
        meta = _meta(test_case)
        instab = verdict_stability(meta.get("verdicts") or [])
        self.score = 1.0 - instab
        self.success = self.score >= self.threshold
        self.reason = f"stability={self.score}"
        return self.score
