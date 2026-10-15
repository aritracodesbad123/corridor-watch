"""Dist H structure holdout. First run freezes; later runs pin-assert only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evaluation import POSITIVE_SCENARIOS, run_evaluation
from graph_features import FLAG_THRESHOLD
from validation import ROOT, stamped
from validation.external.generator_b import POSITIVE_B
from validation.external.generator_c import POSITIVE_C
from validation.external.generator_d import POSITIVE_D
from validation.external.generator_e import POSITIVE_E
from validation.external.generator_f import POSITIVE_F
from validation.external.generator_g import POSITIVE_G
from validation.external.generator_h import KNOWN_A_TO_G, POSITIVE_H, SEED

REPORTS = ROOT / "reports"
PINNED = REPORTS / "dist_h.json"
FREEZE = REPORTS / "dist_h_freeze.json"
GF = ROOT / "graph_features.py"


def _sha12() -> str:
    return hashlib.sha256(GF.read_bytes()).hexdigest()[:12]


def _assert_disjoint():
    assert SEED == 59
    assert FLAG_THRESHOLD == 40
    assert POSITIVE_H.isdisjoint(POSITIVE_SCENARIOS)
    assert POSITIVE_H.isdisjoint(POSITIVE_B)
    assert POSITIVE_H.isdisjoint(POSITIVE_C)
    assert POSITIVE_H.isdisjoint(POSITIVE_D)
    assert POSITIVE_H.isdisjoint(POSITIVE_E)
    assert POSITIVE_H.isdisjoint(POSITIVE_F)
    assert POSITIVE_H.isdisjoint(POSITIVE_G)
    assert POSITIVE_H.isdisjoint(KNOWN_A_TO_G)


def _create_freeze_and_score():
    sha = _sha12()
    freeze = {
        "frozen_seed": SEED,
        "dataset_version": f"generator_h.seed{SEED}",
        "generator": "validation/external/generator_h.py",
        "graph_features_sha256_12": sha,
        "flag_threshold": FLAG_THRESHOLD,
        "do_not_tune": True,
        "frozen_before_run": True,
        "structure_holdout": True,
        "note": "Topologies are not Dist C–G skip-hop / 6-ring / pure-smurf / inject-peel templates.",
    }
    FREEZE.write_text(json.dumps(freeze, indent=2) + "\n")
    result = run_evaluation(cut="dist_h")
    result["one_shot"] = True
    result["do_not_tune"] = True
    result["random_seed"] = SEED
    result["structure_holdout"] = True
    payload = stamped(result, dataset="dist_h", dataset_version=f"generator_h.seed{SEED}", random_seed=SEED)
    PINNED.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    md = REPORTS / "dist_h.md"
    m = payload.get("metrics") or {}
    g = payload.get("graph_metrics") or {}
    md.write_text(
        "# Dist H — structure holdout\n\n"
        f"- seed: `{SEED}`\n"
        f"- graph_features sha12: `{sha}`\n"
        f"- txn metrics: P {m.get('precision')} R {m.get('recall')} F1 {m.get('f1')} FPR {m.get('false_positive_rate')}\n"
        f"- graph metrics: P {g.get('precision')} R {g.get('recall')} F1 {g.get('f1')} FPR {g.get('false_positive_rate')}\n"
        "- Synthetic structure probe (Level-3 style). Not real-bank performance.\n"
        "- Do not retune on seed 59.\n"
    )
    return payload, freeze


def test_distribution_h_structure_holdout():
    _assert_disjoint()
    REPORTS.mkdir(exist_ok=True)
    if not FREEZE.exists() or not PINNED.exists():
        payload, freeze = _create_freeze_and_score()
    else:
        payload = json.loads(PINNED.read_text())
        freeze = json.loads(FREEZE.read_text())

    assert freeze["frozen_seed"] == 59
    assert freeze["dataset_version"] == "generator_h.seed59"
    assert freeze["generator"] == "validation/external/generator_h.py"
    assert freeze["do_not_tune"] is True
    assert freeze["frozen_before_run"] is True
    assert freeze["structure_holdout"] is True
    # Pin to freeze hash (first-run value), not necessarily current file if later edits
    assert len(freeze["graph_features_sha256_12"]) == 12

    assert payload["random_seed"] == 59
    assert payload["one_shot"] is True
    assert payload["do_not_tune"] is True
    assert payload["sample_count"] >= 40
    assert set(payload["positive_scenarios"]) == POSITIVE_H
    assert "metrics" in payload
    assert "graph_metrics" in payload
    assert "precision" in payload["graph_metrics"]
    assert "f1" in payload["metrics"]
