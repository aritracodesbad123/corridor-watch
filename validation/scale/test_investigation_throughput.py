import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_investigation_throughput_from_live_ingest_artifacts():
    rows = []
    for name in ("test_100_tps.json", "test_500_tps.json", "test_1000_tps.json", "test_2000_tps.json"):
        path = ROOT / "reports" / "scale" / name
        if not path.exists():
            continue
        raw = json.loads(path.read_text())
        elapsed = raw.get("elapsed_seconds") or raw.get("wall_seconds")
        queued = raw.get("queued_for_investigation")
        enqueue_tps = round(queued / elapsed, 2) if queued and elapsed else None
        rows.append({
            "target": raw.get("requested_rate"),
            "queued_for_investigation": queued,
            "elapsed_seconds": elapsed,
            "enqueue_tps": enqueue_tps,
            "completions_per_sec": None,
            "ai_investigations_per_sec": None,
            "gemini_requests_total": raw.get("gemini_requests_total"),
        })
    best = max((r["enqueue_tps"] or 0) for r in rows) if rows else None
    payload = {
        "enqueue_tps": best,
        "completion_tps": None,
        "time_to_verdict": None,
        "note": "Enqueue TPS from ingest artifacts. Completions/AI TPS NOT_MEASURED on these probes.",
        "runs": rows,
    }
    (ROOT / "reports" / "scale" / "investigation_throughput.json").write_text(json.dumps(payload, indent=2))
    assert rows
    assert best is None or best > 0
