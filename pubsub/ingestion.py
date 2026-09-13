"""Idempotent ingestion path. Never calls Gemini. Never walks large graphs."""
from __future__ import annotations

import time
import uuid
from typing import Any

from config import get_settings
from db import connect, init_schema, insert_or_ignore
from metrics import METRICS
from pubsub.schemas import TransactionEvent, utc_now
from risk.tiers import RiskTier, cheap_screen

_schema_ready = False

TXN_COLS = (
    "txn_id", "sender_id", "receiver_id", "amount", "currency", "corridor", "ts",
    "device_id", "session_id", "beneficiary_id", "purpose", "source_of_funds",
    "fraud_scenario", "origin_country", "destination_country", "origin_bank_id",
    "destination_bank_id", "channel", "risk_score", "risk_tier", "status",
)


def _ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    init_schema()
    _schema_ready = True


def _priority(tier: RiskTier) -> int:
    return {"CRITICAL": 100, "HIGH": 80, "MEDIUM": 40, "LOW": 10}[tier.value]


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

    t0 = time.perf_counter()
    inserted_event = insert_or_ignore(
        con,
        "ingestion_events",
        ("message_id", "txn_id", "received_at", "source"),
        (message_id, event.txn_id, utc_now(), source),
        "message_id",
    )
    METRICS.observe("ingest_idempotency", (time.perf_counter() - t0) * 1000.0)
    if not inserted_event:
        if own:
            con.close()
        METRICS.inc("transactions_duplicate_total")
        METRICS.observe("ingest_total", (time.perf_counter() - started) * 1000.0)
        return {
            "status": "duplicate",
            "message_id": message_id,
            "txn_id": event.txn_id,
            "duplicate": True,
        }

    t0 = time.perf_counter()
    screen = cheap_screen(event.model_dump())
    METRICS.observe("ingest_validate", (time.perf_counter() - t0) * 1000.0)
    row = event.as_row()
    row["risk_score"] = screen.score
    row["risk_tier"] = screen.tier.value
    row["status"] = "accepted"
    queued = False
    queue_id = None
    try:
        t0 = time.perf_counter()
        inserted_txn = insert_or_ignore(
            con, "transactions", TXN_COLS,
            tuple(row[c] for c in TXN_COLS),
            "txn_id",
        )
        METRICS.observe("ingest_transaction_write", (time.perf_counter() - t0) * 1000.0)
        if not inserted_txn:
            if commit:
                con.commit()
            if own:
                con.close()
            METRICS.inc("transactions_duplicate_total")
            METRICS.observe("ingest_total", (time.perf_counter() - started) * 1000.0)
            return {
                "status": "duplicate",
                "message_id": message_id,
                "txn_id": event.txn_id,
                "duplicate": True,
            }
        if screen.tier in {RiskTier.MEDIUM, RiskTier.HIGH, RiskTier.CRITICAL}:
            from investigations.queue import enqueue
            t0 = time.perf_counter()
            queue_id = f"Q-{uuid.uuid4().hex[:10]}"
            enqueue(
                con, queue_id, event.txn_id,
                f"N-{event.sender_account_id[:8]}-{event.receiver_account_id[:8]}",
                screen.tier.value,
                priority=_priority(screen.tier),
            )
            queued = True
            _maybe_flag(con, event, screen)
            METRICS.observe("ingest_queue_write", (time.perf_counter() - t0) * 1000.0)
            METRICS.inc("suspicious_transactions_total")
            METRICS.inc("investigations_started_total")
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
        t0 = time.perf_counter()
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
        METRICS.observe("ingest_publish", (time.perf_counter() - t0) * 1000.0)
    METRICS.inc("transactions_processed_total")
    METRICS.ingestion_latency.add((time.perf_counter() - started) * 1000.0)
    METRICS.observe("ingest_total", (time.perf_counter() - started) * 1000.0)
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


def _maybe_flag(con, event: TransactionEvent, screen) -> None:
    settings = get_settings()
    if screen.score < settings.risk_threshold_medium:
        return
    insert_or_ignore(
        con,
        "flagged_transactions",
        (
            "txn_id", "sender_id", "receiver_id", "amount", "corridor", "ts", "risk_score",
            "primary_pattern", "fraud_scenario", "currency", "purpose", "source_of_funds",
            "risk_tier", "network_id", "workflow_state",
        ),
        (
            event.txn_id, event.sender_account_id, event.receiver_account_id,
            event.amount, event.corridor, event.timestamp, screen.score,
            event.fraud_scenario if event.fraud_scenario != "normal" else "elevated_activity",
            event.fraud_scenario, event.currency, event.purpose, event.source_of_funds,
            screen.tier.value,
            f"N-{event.sender_account_id[:8]}-{event.receiver_account_id[:8]}",
            "open",
        ),
        "txn_id",
    )
