from validation.deepeval.metrics.verdict_stability import verdict_stability


def test_stability_metric_on_repeated_verdicts():
    assert verdict_stability(["monitor"] * 5) <= 0.10
    assert verdict_stability(["monitor", "clear", "monitor", "clear", "escalate_fiu"]) > 0.10
