"""Detector quality on the clean data_gen cut. Independent of Gemini."""


def test_detection_quality_gate(eval_result):
    m = eval_result["metrics"]
    assert m["f1"] == 1.0
    assert m["false_positive_rate"] <= 0.10
    assert eval_result["quality_gate"]["passed"]
