import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOAK = ROOT / "reports" / "scale" / "soak.json"


def test_soak_is_not_claimed_without_artifact():
    if not SOAK.exists():
        SOAK.write_text(json.dumps({
            "1h": "NOT_MEASURED",
            "6h": "NOT_MEASURED",
            "24h": "NOT_MEASURED",
            "note": "Live soak is opt-in. 10-20s probes are not a soak.",
        }, indent=2))
    status = json.loads(SOAK.read_text())
    assert status["1h"] in {"NOT_MEASURED"} or isinstance(status["1h"], dict)
