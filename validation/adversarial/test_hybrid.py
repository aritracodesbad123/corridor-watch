import json
from pathlib import Path

from investigation_dag import run_dag
from pubsub.ingestion import ingest_transaction
from validation.reliability.test_idempotency import _event

ROOT = Path(__file__).resolve().parents[2]

HYBRIDS = [
    ("HYB-MULE-SMURF", 990, 3),
    ("HYB-MULE-DEVICE", 14000, 2),
    ("HYB-SYN-HOP", 11000, 4),
    ("HYB-SPLIT-XCOR", 4800, 6),
]


def test_hybrid_typologies_are_suspicious_without_named_dna(isolated_db):
    detected = 0
    rows = []
    for txn_id, amount, age in HYBRIDS:
        ingest_transaction(
            _event(txn_id=txn_id, source_event_id=f"E-{txn_id}", amount=amount, account_age_days=age),
            message_id=f"m-{txn_id}",
        )
        verdict = run_dag(txn_id, audit_events=False)["verdict"]
        score = float(verdict.get("risk_score") or 0)
        pattern = verdict.get("primary_pattern") or "elevated_activity"
        hit = score >= 40
        detected += int(hit)
        rows.append({"txn_id": txn_id, "score": score, "pattern": pattern, "detected": hit,
                     "uncertain": hit and pattern == "elevated_activity"})
    rate = detected / len(HYBRIDS)
    (ROOT / "reports" / "hybrid.json").write_text(json.dumps({"n": len(HYBRIDS), "detection_rate": rate, "cases": rows}, indent=2))
    assert detected >= 1
