#!/usr/bin/env python3
"""Batched synthetic publisher for ingest benchmarks.

Measures achieved throughput. Never invents a TPS number.

Three distinct modes — do not treat them as equivalent:

  --in-process     call ingest_batch in this process
  --url ...        HTTP POST /api/ingest/batch
  --pubsub         Google Pub/Sub → push subscription → Cloud Run → Cloud SQL

Examples:
  python pubsub_load_generator.py --rate 500 --duration 5 --in-process
  python pubsub_load_generator.py --rate 100 --duration 10 --url http://127.0.0.1:8080/api/ingest/batch
  python pubsub_load_generator.py --pubsub --rate 1000 --duration 20 --command-url https://... --token TOKEN
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from synthetic.publisher import publish_in_process
from synthetic.transaction_generator import generate_events
from synthetic.world import seed_banks


def _get_json(url: str, token: str = "") -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url: str, payload: dict, token: str = "") -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _pubsub_backlog(project: str, subscription: str) -> int | None:
    try:
        from observability import platform_signals
        return platform_signals().get("pubsub_backlog")
    except Exception:
        return None


def run(
    rate: int,
    duration: int,
    batch_size: int,
    seed: int,
    scenario_mix: str,
    in_process: bool,
    url: str,
    token: str,
    pubsub: bool = False,
    command_url: str = "",
    project: str = "",
    topic: str = "corridor-transactions",
    subscription: str = "corridor-transactions-push",
    persist: bool = False,
) -> dict:
    if not pubsub:
        seed_banks()
    total = max(1, rate * duration)
    events = generate_events(total, seed=seed, scenario_mix=scenario_mix)
    since = datetime.now(timezone.utc).isoformat()
    baseline = None
    if command_url:
        try:
            baseline = _get_json(f"{command_url.rstrip('/')}/api/ledger-stats", token)
        except Exception:
            baseline = None

    backlog_start = _pubsub_backlog(project, subscription) if pubsub else None
    started = time.perf_counter()
    accepted = duplicates = failed = queued = published = 0
    offset = 0
    while offset < len(events):
        batch = events[offset:offset + batch_size]
        offset += len(batch)
        target_elapsed = offset / max(rate, 1)
        if pubsub:
            from pubsub.publisher import publish_gcp
            published += publish_gcp(batch, wait=False)
        elif in_process:
            result = publish_in_process(batch, source="loadgen")
            accepted += int(result.get("accepted") or 0)
            duplicates += int(result.get("duplicates") or 0)
            failed += int(result.get("failed") or 0)
            queued += int(result.get("queued") or 0)
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
    publish_elapsed = max(time.perf_counter() - started, 0.001)
    if pubsub:
        from pubsub.publisher import flush_gcp
        flush_gcp()

    drain_seconds = 0.0
    backlog_end = backlog_start
    ledger = None
    command = None
    metrics = None
    base = command_url.rstrip("/") if command_url else ""
    since_q = urllib.parse.quote(since, safe="")

    def _ledger() -> dict | None:
        if not base:
            return None
        try:
            return _get_json(f"{base}/api/ledger-stats?since={since_q}", token)
        except Exception:
            return None

    if pubsub and base and baseline:
        drain_started = time.perf_counter()
        target = max(1, int(published))
        for _ in range(40):
            ledger = _ledger()
            processed_now = 0
            if ledger:
                processed_now = max(
                    0,
                    int(ledger.get("ingestion_events") or 0) - int(baseline.get("ingestion_events") or 0),
                )
            backlog_end = _pubsub_backlog(project, subscription)
            if processed_now >= target:
                break
            time.sleep(1)
        drain_seconds = round(time.perf_counter() - drain_started, 3)
    elif pubsub:
        backlog_end = _pubsub_backlog(project, subscription)

    if command_url:
        ledger = ledger or _ledger()
        try:
            command = _get_json(f"{base}/api/command-center", token)
        except Exception:
            try:
                command = _get_json(f"{base}/api/command-center?light=1", token)
            except Exception:
                command = None
        try:
            metrics = _get_json(f"{base}/api/metrics", token)
        except Exception:
            metrics = None

    wall_seconds = max(time.perf_counter() - started, 0.001)
    elapsed = max(publish_elapsed + drain_seconds, 0.001)
    processed = None
    queued_delta = None
    flagged_delta = None
    if ledger and baseline:
        processed = max(0, int(ledger.get("ingestion_events") or 0) - int(baseline.get("ingestion_events") or 0))
        queued_delta = max(0, int(ledger.get("investigation_queue") or 0) - int(baseline.get("investigation_queue") or 0))
        flagged_delta = max(0, int(ledger.get("flagged_transactions") or 0) - int(baseline.get("flagged_transactions") or 0))
    elif ledger:
        processed = int(ledger.get("since_ingestion_events") or ledger.get("ingestion_events") or 0)

    mode = "pubsub" if pubsub else ("in_process" if in_process else "http")
    latency = (metrics or {}).get("ingestion_latency_ms") or {}
    gemini = ((metrics or {}).get("counters") or {}).get("gemini_requests_total")
    if processed is not None:
        achieved_tps = round(processed / elapsed, 2)
    elif not pubsub:
        achieved_tps = round((accepted + duplicates) / publish_elapsed, 2)
    else:
        achieved_tps = None
    report = {
        "requested_rate": rate,
        "duration_seconds": duration,
        "batch_size": batch_size,
        "events_generated": len(events),
        "published": published if pubsub else len(events),
        "accepted": accepted,
        "duplicates": duplicates,
        "failed": failed,
        "queued_for_investigation": queued_delta if queued_delta is not None else queued,
        "flagged_from_ledger": flagged_delta,
        "processed_from_ledger": processed,
        "publish_elapsed_seconds": round(publish_elapsed, 3),
        "drain_seconds": drain_seconds,
        "elapsed_seconds": round(elapsed, 3),
        "wall_seconds": round(wall_seconds, 3),
        "achieved_publish_tps": round((published or len(events)) / publish_elapsed, 2),
        "achieved_tps": achieved_tps,
        "p50_ingest_ms": latency.get("p50") or (command or {}).get("p50_ingest_ms"),
        "p95_ingest_ms": latency.get("p95") or (command or {}).get("p95_ingest_ms"),
        "p99_ingest_ms": latency.get("p99"),
        "gemini_requests_total": gemini,
        "pubsub_backlog_start": backlog_start,
        "pubsub_backlog_end": backlog_end,
        "cloud_run_instances": (command or {}).get("cloud_run_instances") if command else None,
        "investigation_path": (ledger or command or {}).get("investigation_path"),
        "ledger": ledger,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "topic": topic if pubsub else None,
        "note": "achieved_tps is measured, not claimed. For --pubsub it is ledger processed / wall time including drain. in_process ≠ HTTP ≠ Pub/Sub.",
    }
    if persist and command_url:
        try:
            _post_json(f"{command_url.rstrip('/')}/api/benchmarks", {"kind": "ingest", "payload": report}, token)
            report["persisted"] = True
        except Exception as exc:
            report["persisted"] = False
            report["persist_error"] = str(exc)
    report["result_file"] = _write_result_file(report)
    return report


def _write_result_file(report: dict) -> str:
    """Timestamped local copy. Never write tokens or secrets."""
    from pathlib import Path

    root = Path(__file__).resolve().parent / "benchmarks" / "results"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    mode = str(report.get("mode") or "run").replace("/", "-")
    rate = report.get("requested_rate") or "x"
    path = root / f"{stamp}-{mode}-{rate}tps.json"
    safe = {k: v for k, v in report.items() if k not in {"token", "authorization", "persist_error"}}
    path.write_text(json.dumps(safe, indent=2) + "\n")
    return str(path)


def print_report(report: dict) -> None:
    print("CORRIDOR WATCH LOAD TEST")
    print("────────────────────────────────────")
    print(f"Mode             : {report.get('mode')}")
    print(f"Target TPS       : {report.get('requested_rate')}")
    print(f"Duration         : {report.get('duration_seconds')} sec")
    print()
    print(f"Generated        : {report.get('events_generated')}")
    print(f"Published        : {report.get('published')}")
    print(f"Ledger processed : {report.get('processed_from_ledger')}")
    print(f"Accepted         : {report.get('accepted')}")
    print(f"Duplicates       : {report.get('duplicates')}")
    print(f"Failed           : {report.get('failed')}")
    print(f"Investigations   : {report.get('queued_for_investigation')}")
    print(f"Flagged          : {report.get('flagged_from_ledger')}")
    print()
    print(f"Publish TPS      : {report.get('achieved_publish_tps')}")
    print(f"Achieved TPS     : {report.get('achieved_tps')}")
    print(f"P50 ingest (ms)  : {report.get('p50_ingest_ms')}")
    print(f"P95 ingest (ms)  : {report.get('p95_ingest_ms')}")
    print(f"P99 ingest (ms)  : {report.get('p99_ingest_ms')}")
    print(f"Gemini requests  : {report.get('gemini_requests_total')}")
    print()
    print(f"Pub/Sub backlog  : {report.get('pubsub_backlog_start')} → {report.get('pubsub_backlog_end')}")
    print(f"Cloud Run inst.  : {report.get('cloud_run_instances')}")
    print()
    print(report.get("note"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Corridor Watch load generator")
    parser.add_argument("--rate", type=int, default=100, help="Target events per second")
    parser.add_argument("--duration", type=int, default=5, help="Seconds to generate")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenario-mix", default="default")
    parser.add_argument("--project", default="", help="GCP project for --pubsub")
    parser.add_argument("--topic", default="corridor-transactions")
    parser.add_argument("--subscription", default="corridor-transactions-push")
    parser.add_argument("--in-process", action="store_true", help="Call ingest in-process (local only)")
    parser.add_argument("--pubsub", action="store_true", help="Publish to Google Pub/Sub")
    parser.add_argument("--url", default="http://127.0.0.1:8080/api/ingest/batch")
    parser.add_argument("--command-url", default="", help="Cloud Run base URL for ledger stats")
    parser.add_argument("--token", default="")
    parser.add_argument("--persist", action="store_true", help="POST the measured report to /api/benchmarks")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if args.pubsub:
        import os
        project = args.project or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        if not project:
            parser.error("--pubsub requires --project or GOOGLE_CLOUD_PROJECT")
        args.project = project
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project)
        os.environ.setdefault("ENVIRONMENT", "gcp")
        os.environ.setdefault("TRANSACTION_TOPIC", args.topic)
    report = run(
        args.rate, args.duration, args.batch_size, args.seed, args.scenario_mix,
        args.in_process, args.url, args.token,
        pubsub=args.pubsub, command_url=args.command_url, project=args.project,
        topic=args.topic, subscription=args.subscription, persist=args.persist,
    )
    if args.pretty:
        print_report(report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
