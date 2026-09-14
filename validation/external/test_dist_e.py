"""One-shot Dist E. Artifact is pinned; do not overwrite after detector changes."""
from __future__ import annotations

import json

from evaluation import POSITIVE_SCENARIOS
from graph_features import FLAG_THRESHOLD
from validation import ROOT
from validation.external.generator_b import POSITIVE_B
from validation.external.generator_c import POSITIVE_C
from validation.external.generator_d import POSITIVE_D
from validation.external.generator_e import KNOWN_A_B_C_D, POSITIVE_E, SEED

REPORTS = ROOT / "reports"
PINNED = REPORTS / "dist_e.json"


def test_distribution_e_one_shot_artifact_is_pinned():
    assert SEED == 41
    assert FLAG_THRESHOLD == 40
    assert POSITIVE_E.isdisjoint(POSITIVE_SCENARIOS)
    assert POSITIVE_E.isdisjoint(POSITIVE_B)
    assert POSITIVE_E.isdisjoint(POSITIVE_C)
    assert POSITIVE_E.isdisjoint(POSITIVE_D)
    assert POSITIVE_E.isdisjoint(KNOWN_A_B_C_D)
    payload = json.loads(PINNED.read_text())
    freeze = json.loads((REPORTS / "dist_e_freeze.json").read_text())
    assert payload["random_seed"] == 41
    assert payload["one_shot"] is True
    assert payload["do_not_tune"] is True
    assert payload["sample_count"] >= 80
    assert set(payload["positive_scenarios"]) == POSITIVE_E
    assert payload["metrics"]["recall"] == 1.0
    assert payload["metrics"]["precision"] == 1.0
    assert payload["metrics"]["f1"] == 1.0
    assert payload["metrics"]["false_positive_rate"] == 0.0
    assert freeze["frozen_seed"] == 41
    assert freeze["dataset_version"] == "generator_e.seed41"
    assert freeze["generator"] == "validation/external/generator_e.py"
    assert freeze["graph_features_sha256_12"] == "87fcdbefdd16"
    assert freeze["do_not_tune"] is True
    assert freeze["frozen_before_run"] is True
