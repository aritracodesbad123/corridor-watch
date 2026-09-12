#!/usr/bin/env python3
"""Batched synthetic publisher for ingest benchmarks.

Measures achieved throughput. Never invents a TPS number.

Examples:
  python pubsub_load_generator.py --rate 500 --duration 5 --in-process
  python pubsub_load_generator.py --rate 100 --duration 10 --url http://127.0.0.1:8080/api/ingest/batch
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

from synthetic.publisher import publish_in_process
from synthetic.transaction_generator import generate_events
from synthetic.world import seed_banks


def run(rate: int, duration: int, batch_size: int, seed: int, scenario_mix: str, in_process: bool, url: str, token: str) -> dict:
    seed_banks()
    total = max(1, rate * duration)
    events = generate_events(total, seed=seed, scenario_mix=scenario_mix)
    started = time.perf_counter()
    accepted = duplicates = failed = queued = 0
    offset = 0
    while offset < len(events):
        batch = events[offset:offset + batch_size]
        offset += len(batch)
        target_elapsed = offset / max(rate, 1)
        if in_process:
            result = publish_in_process(batch, source="loadgen")
        else:
            from pubsub.publisher import publish_local
            result = publish_local(batch, ingest_url=url, token=token)
        accepted += int(result.get("accepted") or 0)
        duplicates += int(result.get("duplicates") or 0)
        failed += int(result.get("failed") or 0)
        queued += int(result.get("queued") or 0)
        sleep_for = target_elapsed - (time.perf_counter() - started)
        if sleep_for > 0:
            time.sleep(sleep_for)
    elapsed = max(time.perf_counter() - started, 0.001)
    report = {
        "requested_rate": rate,
        "duration_seconds": duration,
        "batch_size": batch_size,
        "events_generated": len(events),
        "accepted": accepted,
        "duplicates": duplicates,
        "failed": failed,
        "queued_for_investigation": queued,
        "elapsed_seconds": round(elapsed, 3),
        "achieved_tps": round(len(events) / elapsed, 2),
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "mode": "in_process" if in_process else "http",
        "note": "achieved_tps is measured, not a marketing claim.",
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Corridor Watch load generator")
    parser.add_argument("--rate", type=int, default=100, help="Target events per second")
    parser.add_argument("--duration", type=int, default=5, help="Seconds to generate")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenario-mix", default="default")
    parser.add_argument("--project", default="", help="Unused locally; reserved for GCP topic publish")
    parser.add_argument("--topic", default="corridor-transactions")
    parser.add_argument("--in-process", action="store_true", help="Call ingest in-process (highest local throughput)")
    parser.add_argument("--url", default="http://127.0.0.1:8080/api/ingest/batch")
    parser.add_argument("--token", default="")
    args = parser.parse_args()
    report = run(
        args.rate, args.duration, args.batch_size, args.seed, args.scenario_mix,
        args.in_process, args.url, args.token,
    )
    import json
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
