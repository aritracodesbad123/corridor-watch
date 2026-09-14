import deepeval

from validation.deepeval.runner import run_offline


def test_deepeval_package_imports():
    assert deepeval.__version__


def test_deepeval_offline_runner_writes_artifact():
    payload = run_offline()
    assert payload["case_count"] >= 1
    assert payload["cases"][0]["scores"]["AmlCorrectnessMetric"]["success"]
