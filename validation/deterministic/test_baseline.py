def test_graph_beats_transaction_baseline(eval_result):
    graph_f1 = eval_result["metrics"]["f1"]
    base_f1 = eval_result["baseline_comparison"]["metrics"]["f1"]
    assert graph_f1 >= base_f1 + 0.10
