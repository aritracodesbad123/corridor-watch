"""One-shot Dist C. Artifact is pinned; do not overwrite after detector changes."""
from __future__ import annotations

import json

from evaluation import POSITIVE_SCENARIOS
from graph_features import FLAG_THRESHOLD
from validation import ROOT
from validation.external.generator_b import POSITIVE_B
from validation.external.generator_c import KNOWN_A_B, POSITIVE_C, SEED

REPORTS = ROOT / "reports"
PINNED = REPORTS / "dist_c.json"


def test_distribution_c_one_shot_artifact_is_pinned():
    assert SEED == 23
    assert FLAG_THRESHOLD == 40
    assert POSITIVE_C.isdisjoint(POSITIVE_SCENARIOS)
    assert POSITIVE_C.isdisjoint(POSITIVE_B)
    assert POSITIVE_C.isdisjoint(KNOWN_A_B)
    payload = json.loads(PINNED.read_text())
    freeze = json.loads((REPORTS / "dist_c_freeze.json").read_text())
    assert payload["random_seed"] == 23
    assert payload["one_shot"] is True
    assert payload["metrics"]["recall"] == 1.0
    assert payload["metrics"]["f1"] == 0.5
    assert payload["metrics"]["false_positive_rate"] == 0.7568
    assert freeze["frozen_seed"] == 23
    assert freeze["graph_features_sha256_12"] == "26fbe680d558"
    assert freeze["do_not_tune"] is True
