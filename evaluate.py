#!/usr/bin/env python3
"""Reproducible evaluator. All numbers come from an actual run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation import persist_benchmark, run_evaluation
from graph.corridor import investigation_compression
from pubsub_load_generator import run as run_load


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["detection", "ingest", "both"], default="detection")
    parser.add_argument("--rate", type=int, default=200)
    parser.add_argument("--duration", type=int, default=3)
    parser.add_argument("--scenario-mix", default="default")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--write", default="benchmarks/latest.json")
    args = parser.parse_args()

    out: dict = {"mode": args.mode}
    if args.mode in {"detection", "both"}:
        out["detection"] = run_evaluation()
        out["investigation_compression"] = investigation_compression()
        persist_benchmark("detection", out["detection"])
        persist_benchmark("compression", out["investigation_compression"])
    if args.mode in {"ingest", "both"}:
        out["ingest"] = run_load(
            args.rate, args.duration, args.batch_size, 42, args.scenario_mix, True, "", ""
        )
        persist_benchmark("ingest", out["ingest"])
    if args.write:
        path = Path(args.write)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
