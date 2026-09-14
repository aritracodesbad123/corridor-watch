import json
from pathlib import Path

from risk.tiers import cheap_screen, RiskTier

ROWS = Path(__file__).resolve().parents[1] / "datasets" / "hard_negatives.jsonl"


def test_established_accounts_are_not_all_critical():
    flagged = 0
    total = 0
    for line in ROWS.read_text().splitlines():
        row = json.loads(line)
        total += 1
        screen = cheap_screen({
            "amount": row["amount"],
            "account_age_days": row["account_age_days"],
            "fraud_scenario": "normal",
            "origin_country": "IN",
            "destination_country": "SG",
        })
        if screen.tier in {RiskTier.HIGH, RiskTier.CRITICAL}:
            flagged += 1
    assert total
    assert flagged / total <= 0.08 or flagged == 0
