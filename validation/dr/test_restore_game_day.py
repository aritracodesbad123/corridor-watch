"""RTO/RPO from a timed Cloud SQL clone. Do not invent minutes."""
import json
from pathlib import Path

import pytest

REPORT = Path(__file__).resolve().parents[2] / "reports" / "dr_gameday.json"


@pytest.mark.skipif(not REPORT.exists(), reason="run ./scripts/dr_game_day.sh PROJECT first")
def test_rto_rpo_measured():
    status = json.loads(REPORT.read_text())
    assert status["rto_minutes"] is not None
    assert status["rpo_minutes"] is not None
    assert status.get("pitr_to_past_rpo") == "NOT_MEASURED"
    assert status.get("duplicates_after_replay") in {None, "NOT_MEASURED"}
    assert status["label"] == "Measured"
