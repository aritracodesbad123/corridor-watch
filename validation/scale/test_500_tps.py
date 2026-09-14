import os

import pytest

from validation.scale.live import GATES, run_live


@pytest.mark.skipif(not os.getenv("CW_SCALE_LIVE"), reason="nightly live Pub/Sub path")
def test_500_tps_sustained():
    report = run_live(500)
    assert report["achieved_tps"] is not None
    assert report["achieved_tps"] >= GATES[500], (
        f"measured consume {report['achieved_tps']} TPS < {GATES[500]}"
    )
