"""One-shot Dist F. Artifact is pinned; do not overwrite after detector changes."""
from __future__ import annotations

import json

from evaluation import POSITIVE_SCENARIOS
from graph_features import FLAG_THRESHOLD
from validation import ROOT
from validation.external.generator_b import POSITIVE_B
from validation.external.generator_c import POSITIVE_C
from validation.external.generator_d import POSITIVE_D
from validation.external.generator_e import POSITIVE_E
from validation.external.generator_f import FAMILY, KNOWN_A_TO_E, POSITIVE_F, SEED

REPORTS = ROOT / "reports"
PINNED = REPORTS / "dist_f.json"


def test_distribution_f_one_shot_artifact_is_pinned():
    assert SEED == 47
    assert FLAG_THRESHOLD == 40
    assert POSITIVE_F.isdisjoint(POSITIVE_SCENARIOS)
    assert POSITIVE_F.isdisjoint(POSITIVE_B)
    assert POSITIVE_F.isdisjoint(POSITIVE_C)
    assert POSITIVE_F.isdisjoint(POSITIVE_D)
    assert POSITIVE_F.isdisjoint(POSITIVE_E)
    assert POSITIVE_F.isdisjoint(KNOWN_A_TO_E)
    assert set(FAMILY) <= POSITIVE_F
    assert "trade_overbill" not in FAMILY
    payload = json.loads(PINNED.read_text())
    freeze = json.loads((REPORTS / "dist_f_freeze.json").read_text())
    assert payload["random_seed"] == 47
    assert payload["one_shot"] is True
    assert payload["do_not_tune"] is True
    assert payload["sample_count"] >= 80
    assert set(payload["positive_scenarios"]) == POSITIVE_F
    assert payload["metrics"]["recall"] == 1.0
    assert payload["metrics"]["precision"] == 1.0
    assert payload["metrics"]["f1"] == 1.0
    assert payload["metrics"]["false_positive_rate"] == 0.0
    assert payload["pattern_accuracy"] == 0.0
    assert payload["taxonomy_accuracy"] == 0.25
    assert payload["mapping_coverage"] == 0.75
    assert payload["novel_detection_recall"] == 1.0
    assert payload["family_map"] == FAMILY
    assert freeze["frozen_seed"] == 47
    assert freeze["graph_features_sha256_12"] == "34a3e1a3dff0"
    assert freeze["do_not_tune"] is True
    assert freeze["frozen_before_run"] is True
