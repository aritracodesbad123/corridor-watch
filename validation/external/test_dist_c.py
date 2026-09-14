"""One-shot Dist C. Freeze detector first; do not retune on seed 23."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evaluation import POSITIVE_SCENARIOS, run_evaluation
from graph_features import FLAG_THRESHOLD
from validation import ROOT, stamped
from validation.external.generator_b import POSITIVE_B
from validation.external.generator_c import KNOWN_A_B, POSITIVE_C, SEED

REPORTS = ROOT / "reports"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def test_distribution_c_is_frozen_one_shot_holdout():
    freeze = {
        "frozen_before_run": True,
        "one_shot": True,
        "do_not_tune": True,
        "frozen_seed": SEED,
        "flag_threshold": FLAG_THRESHOLD,
        "graph_features_sha256_12": _sha(ROOT / "graph_features.py"),
        "note": "Recorded before scoring. Do not edit graph_features.py to pass this seed.",
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "dist_c_freeze.json").write_text(json.dumps(stamped(freeze, dataset="dist_c_freeze", random_seed=SEED), indent=2))

    assert SEED == 23
    assert FLAG_THRESHOLD == 40
    assert POSITIVE_C.isdisjoint(POSITIVE_SCENARIOS)
    assert POSITIVE_C.isdisjoint(POSITIVE_B)
    assert POSITIVE_C.isdisjoint(KNOWN_A_B)

    result = run_evaluation(cut="dist_c")
    assert result["status"] == "ok"
    assert result["benchmark"] == "dist_c"
    assert set(result["positive_scenarios"]) == POSITIVE_C
    assert result["sample_count"] >= 80
    for name in POSITIVE_C:
        assert name in result["per_scenario"]
    payload = stamped(
        {**result, "freeze": freeze, "one_shot": True, "do_not_tune": True},
        dataset="dist_c",
        dataset_version="generator_c.seed23",
        random_seed=SEED,
    )
    (REPORTS / "dist_c.json").write_text(json.dumps(payload, indent=2, default=str))
    (REPORTS / "dist_c.md").write_text(
        "# Dist C (frozen one-shot)\n\n"
        f"seed `{SEED}` threshold `{FLAG_THRESHOLD}` n={payload['sample_count']}\n\n"
        f"precision={payload['metrics']['precision']} recall={payload['metrics']['recall']} "
        f"f1={payload['metrics']['f1']} FPR={payload['metrics']['false_positive_rate']}\n\n"
        f"TP={payload['metrics']['tp']} FP={payload['metrics']['fp']} "
        f"FN={payload['metrics']['fn']} TN={payload['metrics']['tn']}\n\n"
        "Unseen fraud: layering_cascade (partial hop dropped), dormant_wake, funnel_exit, mirror_peel.\n"
        "Normals: bipartite market, remittance mesh, FX hedge, JPY payroll, noise, "
        "ambiguous tuition/charity inbound. Runtime ignores fraud_scenario.\n"
        "Do not retune the detector on this seed.\n"
    )
    m = result["metrics"]
    assert m["precision"] is not None
    assert m["recall"] is not None
    assert m["false_positive_rate"] is not None
