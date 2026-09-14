from evaluation import POSITIVE_SCENARIOS


def test_each_typology_recall(eval_result):
    for name in POSITIVE_SCENARIOS:
        stats = eval_result["per_scenario"].get(name)
        assert stats, f"missing {name}"
        assert stats["flag_rate"] >= 0.75, f"{name} recall {stats['flag_rate']} < 0.75"
