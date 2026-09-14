from validation.datasets.golden import REQUIRED_KINDS, cases, write_jsonl


def test_golden_set_has_at_least_200_mixed_cases():
    rows = cases()
    write_jsonl()
    kinds = {r["kind"] for r in rows}
    assert len(rows) >= 200
    assert REQUIRED_KINDS <= kinds
