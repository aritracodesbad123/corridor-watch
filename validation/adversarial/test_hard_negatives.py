import json
from pathlib import Path

from investigation_dag import run_dag
from pubsub.ingestion import ingest_transaction
from risk.tiers import RiskTier, cheap_screen
from validation.reliability.test_idempotency import _event

ROOT = Path(__file__).resolve().parents[2]
ROWS = ROOT / "validation" / "datasets" / "hard_negatives.jsonl"


def test_established_accounts_are_not_all_critical(isolated_db):
    flagged = 0
    dag_fp = 0
    total = 0
    kinds = []
    for line in ROWS.read_text().splitlines():
        row = json.loads(line)
        total += 1
        screen = cheap_screen({
            "amount": row["amount"],
            "account_age_days": row["account_age_days"],
            "origin_country": row.get("origin_country", "IN"),
            "destination_country": row.get("destination_country", "SG"),
        })
        ingest_transaction(
            _event(
                txn_id=row["txn_id"],
                source_event_id=f"E-{row['txn_id']}",
                amount=row["amount"],
                account_age_days=row["account_age_days"],
                origin_country=row.get("origin_country", "IN"),
                destination_country=row.get("destination_country", "SG"),
            ),
            message_id=f"m-{row['txn_id']}",
        )
        verdict = run_dag(row["txn_id"], audit_events=False)["verdict"]
        if screen.tier in {RiskTier.HIGH, RiskTier.CRITICAL}:
            flagged += 1
        if float(verdict.get("risk_score") or 0) >= 40:
            dag_fp += 1
        kinds.append(row.get("kind"))
    fpr = flagged / total if total else 0.0
    dag_fpr = dag_fp / total if total else 0.0
    assert total >= 6
    assert fpr <= 0.08 or flagged == 0
    assert dag_fpr <= 0.25
