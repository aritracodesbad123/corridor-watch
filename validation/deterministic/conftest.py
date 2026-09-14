import pytest


@pytest.fixture(scope="module")
def eval_result():
    from evaluation import run_evaluation
    result = run_evaluation(cut="clean")
    assert result["status"] == "ok"
    return result
