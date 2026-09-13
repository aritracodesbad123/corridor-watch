"""Idempotent ingestion path. Never calls Gemini. Never walks large graphs."""
from __future__ import annotations

import time
import uuid
from typing import Any

from config import get_settings
from db import connect, init_schema
from metrics import METRICS
from pubsub.schemas import TransactionEvent, utc_now
from risk.tiers import RiskTier, cheap_screen

_schema_ready = False


def _ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    init_schema()
    _schema_ready = True


def ingest_transaction(
    event: TransactionEvent,
    *,
    message_id: str | None = None,
    source: str = "http",
    con=None,
    commit: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    METRICS.inc("transactions_received_total")
    _ensure_schema()
    message_id = message_id or event.txn_id
    own = con is None
    if own:
        con = connect(purpose="ingest")
    existing = con.execute(
        "SELECT message_id, txn_id FROM ingestion_events WHERE message_id=?",
        (message_id,),
    ).fetchone()
    if existing:
        if own:
            con.close()
        METRICS.inc("transactions_duplicate_total")
        return {
            "status": "duplicate",
            "message_id": message_id,
            "txn_id": existing["txn_id"],
            "duplicate": True,
        }

    prior_txn = con.execute(
        "SELECT txn_id FROM transactions WHERE txn_id=?", (event.txn_id,)
    ).fetchone()
    if prior_txn:
        con.execute(
            "INSERT INTO ingestion_events (message_id, txn_id, received_at, source) VALUES (?,?,?,?)",
            (message_id, event.txn_id, utc_now(), source),
        )
        if commit:
            con.commit()
        if own:
            con.close()
        METRICS.inc("transactions_duplicate_total")
        return {
            "status": "duplicate",
            "message_id": message_id,
            "txn_id": event.txn_id,
            "duplicate": True,
        }

    screen = cheap_screen(event.model_dump())
    row = event.as_row()
    row["risk_score"] = screen.score
    row["risk_tier"] = screen.tier.value
    row["status"] = "accepted"
    try:
        con.execute(
            """INSERT INTO transactions (
                txn_id, sender_id, receiver_id, amount, currency, corridor, ts,
                device_id, session_id, beneficiary_id, purpose, source_of_funds,
                fraud_scenario, origin_country, destination_country, origin_bank_id,
                destination_bank_id, channel, risk_score, risk_tier, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row["txn_id"], row["sender_id"], row["receiver_id"], row["amount"],
                row["currency"], row["corridor"], row["ts"], row["device_id"],
                row["session_id"], row["beneficiary_id"], row["purpose"],
                row["source_of_funds"], row["fraud_scenario"], row["origin_country"],
                row["destination_country"], row["origin_bank_id"],
                row["destination_bank_id"], row["channel"], row["risk_score"],
                row["risk_tier"], row["status"],
            ),
        )
        con.execute(
            "INSERT INTO ingestion_events (message_id, txn_id, received_at, source) VALUES (?,?,?,?)",
            (message_id, event.txn_id, utc_now(), source),
        )
        queued = False
        queue_id = None
        if screen.tier in {RiskTier.MEDIUM, RiskTier.HIGH, RiskTier.CRITICAL}:
            queue_id = _enqueue_investigation(con, event, screen.tier)
            queued = True
            _maybe_flag(con, event, screen)
            METRICS.inc("suspicious_transactions_total")
        if commit:
            con.commit()
    except Exception:
        METRICS.inc("transactions_failed_total")
        if own:
            con.close()
        raise

    if own:
        con.close()
    if queued and queue_id:
        try:
            from pubsub.publisher import notify_investigation
            notify_investigation({
                "queue_id": queue_id,
                "txn_id": event.txn_id,
                "risk_tier": screen.tier.value,
                "durable_store": "investigation_queue",
            })
        except Exception:
            pass
    METRICS.inc("transactions_processed_total")
    METRICS.ingestion_latency.add((time.perf_counter() - started) * 1000.0)
    return {
        "status": "accepted",
        "message_id": message_id,
        "txn_id": event.txn_id,
        "risk_score": screen.score,
        "risk_tier": screen.tier.value,
        "signals": screen.signals,
        "queued_for_investigation": queued,
        "queue_id": queue_id,
        "duplicate": False,
        "gemini_invoked": False,
    }


def ingest_batch(events: list[tuple[TransactionEvent, str | None]], *, source: str = "http") -> dict:
    accepted = 0
    duplicates = 0
    failed = 0
    queued = 0
    results = []
    _ensure_schema()
    con = connect(purpose="ingest")
    try:
        for i, (event, message_id) in enumerate(events, start=1):
            try:
                result = ingest_transaction(
                    event, message_id=message_id, source=source, con=con, commit=False
                )
                results.append(result)
                if result.get("duplicate"):
                    duplicates += 1
                else:
                    accepted += 1
                    if result.get("queued_for_investigation"):
                        queued += 1
                if i % 100 == 0:
                    con.commit()
            except Exception as exc:
                failed += 1
                results.append({"status": "error", "txn_id": event.txn_id, "error": str(exc)})
        con.commit()
    finally:
        con.close()
    return {
        "accepted": accepted,
        "duplicates": duplicates,
        "failed": failed,
        "queued": queued,
        "results": results,
    }


def _enqueue_investigation(con, event: TransactionEvent, tier: RiskTier) -> str:
    queue_id = f"Q-{uuid.uuid4().hex[:10]}"
    now = utc_now()
    network_id = f"N-{event.sender_account_id[:8]}-{event.receiver_account_id[:8]}"
    con.execute(
        """INSERT INTO investigation_queue
           (queue_id, txn_id, network_id, risk_tier, status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?)""",
        (queue_id, event.txn_id, network_id, tier.value, "pending", now, now),
    )
    METRICS.inc("investigations_started_total")
    return queue_id


def _maybe_flag(con, event: TransactionEvent, screen) -> None:
    settings = get_settings()
    if screen.score < settings.risk_threshold_medium:
        return
    existing = con.execute(
        "SELECT txn_id FROM flagged_transactions WHERE txn_id=?", (event.txn_id,)
    ).fetchone()
    if existing:
        return
    con.execute(
        """INSERT INTO flagged_transactions (
            txn_id, sender_id, receiver_id, amount, corridor, ts, risk_score,
            primary_pattern, fraud_scenario, currency, purpose, source_of_funds,
            risk_tier, network_id, workflow_state
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            event.txn_id, event.sender_account_id, event.receiver_account_id,
            event.amount, event.corridor, event.timestamp, screen.score,
            event.fraud_scenario if event.fraud_scenario != "normal" else "elevated_activity",
            event.fraud_scenario, event.currency, event.purpose, event.source_of_funds,
            screen.tier.value,
            f"N-{event.sender_account_id[:8]}-{event.receiver_account_id[:8]}",
            "open",
        ),
    )
