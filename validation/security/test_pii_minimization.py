import json

from privacy import minimize_txn, token_for


def test_raw_account_id_not_in_model_payload():
    raw = minimize_txn({"txn_id": "T1", "sender_id": "ACC-SECRET", "receiver_id": "ACC-B", "amount": 100})
    blob = json.dumps(raw)
    assert "ACC-SECRET" not in blob
    assert raw["sender_account"] == token_for("ACC-SECRET", "account")
