"""One-shot Dist D. Artifact is pinned; do not overwrite after detector changes."""
from __future__ import annotations

import json

from evaluation import POSITIVE_SCENARIOS
from graph_features import FLAG_THRESHOLD
from validation import ROOT
from validation.external.generator_b import POSITIVE_B
from validation.external.generator_c import POSITIVE_C
from validation.external.generator_d import KNOWN_A_B_C, POSITIVE_D, SEED

REPORTS = ROOT / "reports"
PINNED = REPORTS / "dist_d.json"


def test_distribution_d_one_shot_artifact_is_pinned():
    assert SEED == 37
    assert FLAG_THRESHOLD == 40
    assert POSITIVE_D.isdisjoint(POSITIVE_SCENARIOS)
    assert POSITIVE_D.isdisjoint(POSITIVE_B)
    assert POSITIVE_D.isdisjoint(POSITIVE_C)
    assert POSITIVE_D.isdisjoint(KNOWN_A_B_C)
    payload = json.loads(PINNED.read_text())
    freeze = json.loads((REPORTS / "dist_d_freeze.json").read_text())
    assert payload["random_seed"] == 37
    assert payload["one_shot"] is True
    assert payload["do_not_tune"] is True
    assert payload["sample_count"] >= 80
    assert set(payload["positive_scenarios"]) == POSITIVE_D
    assert payload["metrics"]["recall"] == 1.0
    assert payload["metrics"]["f1"] == 0.7397
    assert payload["metrics"]["precision"] == 0.587
    assert payload["metrics"]["false_positive_rate"] == 0.3585
    assert freeze["frozen_seed"] == 37
    assert freeze["graph_features_sha256_12"] == "50938d088d57"
    assert freeze["do_not_tune"] is True
    assert freeze["frozen_before_run"] is True
