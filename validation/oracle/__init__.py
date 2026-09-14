"""Hidden evaluation labels. Runtime detectors must not read these."""
from __future__ import annotations


def extract(rows: list[dict], positive: set[str]) -> dict[str, dict]:
    labels = {}
    for row in rows:
        label = row.get("fraud_scenario") or "normal"
        labels[row["txn_id"]] = {"label": label, "positive": label in positive}
    return labels


def is_positive(txn_id: str, labels: dict[str, dict]) -> bool:
    return bool((labels.get(txn_id) or {}).get("positive"))


def label_of(txn_id: str, labels: dict[str, dict]) -> str:
    return (labels.get(txn_id) or {}).get("label") or "normal"
