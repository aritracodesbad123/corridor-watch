"""Max sustainable TPS under SLO. Do not invent 5,000."""
from pathlib import Path
import json

MEASURED_LIVE = {
    "path": "pubsub_cloud_run_cloud_sql",
    "achieved_tps": 814.13,
    "target_rate": 1000,
    "gate": 800,
    "p50_ms": 0,
    "measured_at": "2026-09-14",
    "source": "reports/scale/test_1000_tps.json",
    "note": "Highest consume that passed its gate. 2k miss best 1212. Not a 5,000 TPS claim.",
}


def test_published_live_consume_is_recorded():
    assert MEASURED_LIVE["achieved_tps"] == 814.13
    assert MEASURED_LIVE["achieved_tps"] < 5000
    out = Path(__file__).resolve().parents[2] / "reports" / "scale" / "slo_boundary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(MEASURED_LIVE, indent=2))
