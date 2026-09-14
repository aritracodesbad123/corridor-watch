from validation.datasets.golden import cases, write_jsonl


def test_golden_set_has_at_least_100_mixed_cases():
    rows = cases()
    write_jsonl()
    kinds = {r["kind"] for r in rows}
    assert len(rows) >= 100
    assert {"mule", "hop", "normal", "hardneg", "hybrid", "partial", "adversarial"} <= kinds
