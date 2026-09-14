import json
from pathlib import Path

from evaluation import run_evaluation
from validation import ROOT
from validation.external.generator_b import POSITIVE_B


def test_distribution_b_is_not_data_gen():
    result = run_evaluation(cut="dist_b")
    assert result["status"] == "ok"
    assert result["benchmark"] == "dist_b"
    assert set(result["positive_scenarios"]) == POSITIVE_B
    assert "mule_pass_through" not in result["per_scenario"]
    (ROOT / "reports" / "dist_b.json").write_text(json.dumps(result, indent=2, default=str))
    assert result["sample_count"] >= 50
