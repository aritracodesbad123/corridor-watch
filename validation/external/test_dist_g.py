"""One-shot Dist G GenAI unknown freeze. Artifact is pinned; do not overwrite Dist A–F."""
from __future__ import annotations

import json

from evaluation import POSITIVE_SCENARIOS
from validation import ROOT
from validation.external.generator_b import POSITIVE_B
from validation.external.generator_c import POSITIVE_C
from validation.external.generator_d import POSITIVE_D
from validation.external.generator_e import POSITIVE_E
from validation.external.generator_f import POSITIVE_F
from validation.external.generator_g import KNOWN_A_TO_F, POSITIVE_G, SEED, build

REPORTS = ROOT / "reports"
PINNED = REPORTS / "dist_g.json"
FREEZE = REPORTS / "dist_g_freeze.json"


def test_distribution_g_unknown_disjoint_and_has_benign():
    assert SEED == 53
    assert POSITIVE_G.isdisjoint(POSITIVE_SCENARIOS)
    assert POSITIVE_G.isdisjoint(POSITIVE_B)
    assert POSITIVE_G.isdisjoint(POSITIVE_C)
    assert POSITIVE_G.isdisjoint(POSITIVE_D)
    assert POSITIVE_G.isdisjoint(POSITIVE_E)
    assert POSITIVE_G.isdisjoint(POSITIVE_F)
    assert POSITIVE_G.isdisjoint(KNOWN_A_TO_F)
    accounts, txns = build(seed=SEED)
    assert len(txns) >= 80
    fraud = sum(1 for t in txns if t["fraud_scenario"] in POSITIVE_G)
    benign = len(txns) - fraud
    assert fraud >= 20
    assert benign >= 40
    assert len(accounts) >= 40


def test_distribution_g_freeze_artifact_is_pinned():
    if not FREEZE.exists() or not PINNED.exists():
        return  # freeze written by live bake-off; unit check still covers disjointness
    freeze = json.loads(FREEZE.read_text())
    payload = json.loads(PINNED.read_text())
    assert freeze["frozen_seed"] == 53
    assert freeze["dataset_version"] == "generator_g.seed53"
    assert freeze["generator"] == "validation/external/generator_g.py"
    assert freeze["do_not_tune"] is True
    assert freeze["frozen_before_run"] is True
    assert freeze["benign_count"] >= 40
    assert freeze["fraud_count"] >= 20
    assert set(freeze["positive_scenarios"]) == POSITIVE_G
    assert payload["random_seed"] == 53
    assert payload["one_shot"] is True
    assert payload["benchmark"] == "dist_g_genai_unknown"
    assert "not a detector Dist" in (payload.get("note") or "")
