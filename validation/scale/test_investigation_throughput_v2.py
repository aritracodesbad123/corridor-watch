import json
import os
import statistics
import time
from pathlib import Path

from investigations.queue import counts
from investigations.service import build_investigation, process_queue_item
from pubsub.ingestion import ingest_transaction
from validation.reliability.test_idempotency import _event

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"


def _pct(xs, p):
    if not xs:
        return None
    s = sorted(xs)
    return round(s[min(len(s) - 1, int(round((p / 100) * (len(s) - 1))))], 1)


def _ingest_implied():
    rows = []
    for name in ("test_100_tps.json", "test_500_tps.json", "test_1000_tps.json", "test_2000_tps.json"):
        path = REPORTS / "scale" / name
        if not path.exists():
            continue
        raw = json.loads(path.read_text())
        queued = raw.get("queued_for_investigation") or 0
        processed = raw.get("processed_from_ledger") or raw.get("events_generated") or 0
        elapsed = raw.get("elapsed_seconds") or raw.get("wall_seconds")
        alert_rate = round(queued / processed, 4) if processed else None
        rows.append({
            "target": raw.get("requested_rate"),
            "achieved_ingest_tps": raw.get("achieved_tps"),
            "queued_for_investigation": queued,
            "processed": processed,
            "elapsed_seconds": elapsed,
            "inferred_alert_rate": alert_rate,
            "implied_investigation_tps": round((raw.get("achieved_tps") or 0) * alert_rate, 2) if alert_rate else None,
            "note": "Alert rate inferred from queued/processed. Load gen did not tag a 5% mix.",
        })
    return rows


def _run_policy(n: int, *, policy: str, use_gemini: bool, worker: str) -> dict:
    from db import connect

    t_enq = time.perf_counter()
    for i in range(n):
        ingest_transaction(
            _event(
                txn_id=f"{policy}-{i}",
                source_event_id=f"E-{policy}-{i}",
                amount=15000,
                account_age_days=2,
                sender_account_id=f"S-{policy}-{i}",
                receiver_account_id=f"R-{policy}-{i}",
            ),
            message_id=f"m-{policy}-{i}",
        )
    enqueue_s = time.perf_counter() - t_enq
    depth = counts()
    latencies = []
    t_run = time.perf_counter()
    completed = 0
    if use_gemini:
        while True:
            started = time.perf_counter()
            result = process_queue_item(worker_id=worker)
            if result.get("status") == "empty":
                break
            latencies.append((time.perf_counter() - started) * 1000.0)
            completed += 1
    else:
        con = connect()
        queued = [dict(r) for r in con.execute(
            "SELECT queue_id, txn_id FROM investigation_queue WHERE status='QUEUED'"
        ).fetchall()]
        con.close()
        for item in queued:
            started = time.perf_counter()
            build_investigation(item["txn_id"], use_gemini=False)
            from investigations.queue import mark_completed
            mark_completed(item["queue_id"])
            latencies.append((time.perf_counter() - started) * 1000.0)
            completed += 1
    run_s = time.perf_counter() - t_run
    return {
        "policy": policy,
        "n": n,
        "use_gemini": use_gemini,
        "enqueue_tps": round(n / enqueue_s, 2) if enqueue_s else None,
        "completion_tps": round(completed / run_s, 2) if run_s else None,
        "completed": completed,
        "queue_depth_after_enqueue": depth,
        "time_to_verdict_ms": {
            "p50": _pct(latencies, 50),
            "p95": _pct(latencies, 95),
            "p99": _pct(latencies, 99),
            "mean": round(statistics.mean(latencies), 1) if latencies else None,
        },
    }


def test_investigation_completion_throughput(isolated_db, monkeypatch):
    import agent
    monkeypatch.setattr(agent, "gemini_available", lambda: False)
    policy_a = _run_policy(40, policy="A", use_gemini=False, worker="tput-a")
    policy_b = {
        "policy": "B",
        "use_gemini": True,
        "completion_tps": None,
        "time_to_verdict_ms": None,
        "note": "NOT_MEASURED unless CW_GEMINI_LIVE=1",
    }
    if os.getenv("CW_GEMINI_LIVE") == "1":
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT") or "corridor-watch-508420")
        if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
            monkeypatch.setenv("GEMINI_BACKEND", "vertex")
            monkeypatch.setenv("VERTEX_LOCATION", os.getenv("VERTEX_LOCATION") or "global")
        monkeypatch.setenv("GEMINI_MODEL", os.getenv("GEMINI_MODEL") or "gemini-2.5-flash")
        agent._client = None
        agent.MODEL = os.environ["GEMINI_MODEL"]
        monkeypatch.setattr(agent, "gemini_available", lambda: True)
        policy_b = _run_policy(10, policy="B", use_gemini=True, worker="tput-b")
    ingest = _ingest_implied()
    payload = {
        "policy_a_deterministic": policy_a,
        "policy_b_gemini": policy_b,
        "sustainable_ingest_tps": 814.13,
        "ingest_ceiling_note": "Keep 814.13 from the passing 1k gate. Not 5,000 TPS. Not four product modes.",
        "implied_load_from_ingest_artifacts": ingest,
        "note": "Completion TPS is investigations finished / drain time, not ingest enqueue TPS.",
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "investigation_throughput_v2.json").write_text(json.dumps(payload, indent=2))
    (REPORTS / "investigation_throughput_v2.md").write_text(
        f"# Investigation throughput v2\n\n"
        f"Policy A completion TPS={policy_a.get('completion_tps')} "
        f"p50={policy_a['time_to_verdict_ms']['p50']}ms "
        f"p95={policy_a['time_to_verdict_ms']['p95']}ms "
        f"p99={policy_a['time_to_verdict_ms']['p99']}ms\n\n"
        f"Policy B Gemini: {policy_b.get('completion_tps') or 'NOT_MEASURED'}\n\n"
        f"Sustainable ingest remains **814.13** TPS (1k gate).\n"
    )
    assert policy_a["completed"] == 40
    assert policy_a["completion_tps"] and policy_a["completion_tps"] > 0
    assert policy_a["time_to_verdict_ms"]["p50"] is not None
    if os.getenv("CW_GEMINI_LIVE") == "1":
        assert policy_b.get("completed") == 10
        assert policy_b.get("completion_tps")
