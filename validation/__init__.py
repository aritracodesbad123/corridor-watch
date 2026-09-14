"""Validation suite. Lives here so it does not shadow evaluation.py."""
from __future__ import annotations

import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

SEED = 42
ROOT = Path(__file__).resolve().parents[1]


def experiment_metadata(**extra) -> dict:
    """Every number in reports/ should carry enough metadata to reproduce the run."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, cwd=ROOT, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        commit = None
    meta = {
        "run_id": extra.pop("run_id", uuid.uuid4().hex[:12]),
        "timestamp_utc": extra.pop("timestamp_utc", datetime.now(timezone.utc).isoformat()),
        "git_commit": extra.pop("git_commit", commit),
        "environment": extra.pop("environment", os.getenv("ENVIRONMENT", "local")),
        "dataset": extra.pop("dataset", "synthetic_v1"),
        "dataset_version": extra.pop("dataset_version", "data_gen.seed42"),
        "model": extra.pop("model", None),
        "model_version": extra.pop("model_version", None),
        "prompt_version": extra.pop("prompt_version", "investigator-v8"),
        "tool_schema_version": extra.pop("tool_schema_version", "investigation-report-v1"),
        "case_count": extra.pop("case_count", 0),
        "random_seed": extra.pop("random_seed", SEED),
    }
    meta.update(extra)
    return meta
