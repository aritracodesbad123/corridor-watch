"""Runtime must not use generator labels, filenames, or Pattern DNA names as features."""
import json

from agent import _safe_evidence
from evaluation import POSITIVE_SCENARIOS
from privacy import minimize_txn, runtime_txn_view
from patterns.matcher import observed_signals
from risk.tiers import cheap_screen
from validation.oracle import extract


def test_filename_is_not_a_label():
    labels = extract(
        [{"txn_id": "mule_pass_through.json", "fraud_scenario": "normal"}],
        POSITIVE_SCENARIOS,
    )
    assert labels["mule_pass_through.json"]["positive"] is False


def test_cheap_screen_ignores_fraud_scenario():
    base = {"amount": 100, "account_age_days": 800, "origin_country": "IN", "destination_country": "SG"}
    labeled = cheap_screen({**base, "fraud_scenario": "mule_pass_through"})
    clean = cheap_screen({**base, "fraud_scenario": "normal"})
    assert labeled.score == clean.score
    assert not any(s.startswith("labeled_") for s in labeled.signals)


def test_matcher_ignores_scenario_name():
    net = {"features": {}}
    labeled = observed_signals({"fraud_scenario": "mule_pass_through", "corridor": "IN->SG"}, net)
    clean = observed_signals({"corridor": "IN->SG"}, net)
    assert labeled == clean


def test_privacy_omits_fraud_scenario():
    out = minimize_txn({"txn_id": "T1", "sender_id": "ACC-1", "fraud_scenario": "mule_pass_through"})
    assert "fraud_scenario" not in out


def test_runtime_txn_view_drops_fraud_scenario():
    out = runtime_txn_view({
        "txn_id": "T1",
        "sender_id": "ACC-1",
        "amount": 100,
        "fraud_scenario": "dock_smurf",
        "fraud_label": 1,
    })
    assert "fraud_scenario" not in out
    assert "fraud_label" not in out
    assert out["txn_id"] == "T1"
    assert out["amount"] == 100


def test_safe_evidence_payload_has_no_fraud_scenario():
    evidence = {
        "transaction": {
            "txn_id": "F-0001-DOC",
            "sender_id": "A",
            "receiver_id": "B",
            "fraud_scenario": "dock_smurf",
            "amount": 500,
        },
        "neighborhood": [],
    }
    safe = _safe_evidence(evidence)
    dumped = json.dumps(safe, default=str)
    assert "fraud_scenario" not in safe["transaction"]
    assert "fraud_scenario" not in dumped
    assert "dock_smurf" not in dumped
