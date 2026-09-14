"""Idempotent ingestion path. Never calls Gemini. Never walks large graphs."""
from __future__ import annotations

import time
import uuid
from typing import Any

from config import get_settings
from db import connect, init_schema, insert_or_ignore, insert_many_or_ignore
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
    from tracing import bind, current
    bind(transaction_id=event.txn_id)
    _ensure_schema()
    message_id = message_id or event.txn_id
    own = con is None
    if own:
        con = connect(purpose="ingest")

    ident = event.identity()
    seen = con.execute(
        "SELECT message_id FROM ingestion_events WHERE source_system=? AND source_event_id=?",
        (ident["source_system"], ident["source_event_id"]),
    ).fetchone()
    t0 = time.perf_counter()
    inserted_event = False if seen else insert_or_ignore(
        con,
        "ingestion_events",
        (
            "message_id", "txn_id", "received_at", "source",
            "event_id", "source_system", "source_event_id", "event_version", "occurred_at",
        ),
        (
            message_id, event.txn_id, utc_now(), source,
            ident["event_id"], ident["source_system"], ident["source_event_id"],
            ident["event_version"], ident["occurred_at"],
        ),
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
            "trace_id": current().get("trace_id") or "",
        }

    t0 = time.perf_counter()
    screen = cheap_screen(event.model_dump(), con=con)
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
                "trace_id": current().get("trace_id") or "",
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
            from pubsub.outbox import enqueue as outbox_enqueue
            outbox_enqueue(con, event_type="investigation_queued", payload={
                "queue_id": queue_id,
                "txn_id": event.txn_id,
                "risk_tier": screen.tier.value,
                "durable_store": "investigation_queue",
                "event_id": ident["event_id"],
                "source_system": ident["source_system"],
                "source_event_id": ident["source_event_id"],
            })
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
        "event_id": ident["event_id"],
        "source_system": ident["source_system"],
        "source_event_id": ident["source_event_id"],
        "trace_id": current().get("trace_id") or "",
    }


def ingest_batch(events: list[tuple[TransactionEvent, str | None]], *, source: str = "http") -> dict:
    accepted = 0
    duplicates = 0
    failed = 0
    queued = 0
    results = []
    _ensure_schema()
    con = connect(purpose="ingest")
    event_rows = []
    txn_rows = []
    queue_events: list[tuple[TransactionEvent, Any]] = []
    try:
        ids = []
        for event, _mid in events:
            ident = event.identity()
            ids.append((ident["source_system"], ident["source_event_id"]))
        seen = set()
        if ids:
            if get_settings().is_postgres:
                qmarks = ",".join(["(?,?)"] * len(ids))
                rows = con.execute(
                    f"SELECT source_system, source_event_id FROM ingestion_events "
                    f"WHERE (source_system, source_event_id) IN ({qmarks})",
                    [x for pair in ids for x in pair],
                ).fetchall()
                seen = {
                    (r["source_system"] if not isinstance(r, tuple) else r[0],
                     r["source_event_id"] if not isinstance(r, tuple) else r[1])
                    for r in rows
                }
            else:
                for src, eid in ids:
                    hit = con.execute(
                        "SELECT 1 FROM ingestion_events WHERE source_system=? AND source_event_id=?",
                        (src, eid),
                    ).fetchone()
                    if hit:
                        seen.add((src, eid))

        for event, message_id in events:
            try:
                ident = event.identity()
                key = (ident["source_system"], ident["source_event_id"])
                if key in seen:
                    duplicates += 1
                    results.append({"status": "duplicate", "txn_id": event.txn_id, "duplicate": True})
                    continue
                seen.add(key)
                message_id = message_id or event.txn_id
                screen = cheap_screen(event.model_dump(), con=con, velocity=False)
                row = event.as_row()
                row["risk_score"] = screen.score
                row["risk_tier"] = screen.tier.value
                row["status"] = "accepted"
                event_rows.append((
                    message_id, event.txn_id, utc_now(), source,
                    ident["event_id"], ident["source_system"], ident["source_event_id"],
                    ident["event_version"], ident["occurred_at"],
                ))
                txn_rows.append(tuple(row[c] for c in TXN_COLS))
                if screen.tier in {RiskTier.MEDIUM, RiskTier.HIGH, RiskTier.CRITICAL}:
                    queue_events.append((event, screen))
                accepted += 1
                results.append({"status": "accepted", "txn_id": event.txn_id, "duplicate": False})
            except Exception as exc:
                failed += 1
                results.append({"status": "error", "txn_id": event.txn_id, "error": str(exc)})

        insert_many_or_ignore(
            con, "ingestion_events",
            ("message_id", "txn_id", "received_at", "source",
             "event_id", "source_system", "source_event_id", "event_version", "occurred_at"),
            event_rows, "message_id",
        )
        insert_many_or_ignore(con, "transactions", TXN_COLS, txn_rows, "txn_id")
        now = utc_now()
        q_rows, flag_rows, out_rows = [], [], []
        skip_outbox = __import__("os").getenv("CW_SKIP_INVESTIGATION_NOTIFY", "").lower() in {"1", "true", "yes"}
        for event, screen in queue_events:
            queue_id = f"Q-{uuid.uuid4().hex[:10]}"
            net = f"N-{event.sender_account_id[:8]}-{event.receiver_account_id[:8]}"
            q_rows.append((queue_id, event.txn_id, net, screen.tier.value, "QUEUED", now, now, _priority(screen.tier), 0))
            flag_rows.append((
                event.txn_id, event.sender_account_id, event.receiver_account_id,
                event.amount, event.corridor, event.timestamp, screen.score,
                event.fraud_scenario if event.fraud_scenario != "normal" else "elevated_activity",
                event.fraud_scenario, event.currency, event.purpose, event.source_of_funds,
                screen.tier.value, net, "open",
            ))
            if not skip_outbox:
                import json as _json
                out_rows.append((
                    f"OB-{uuid.uuid4().hex[:12]}", "investigation_queued",
                    _json.dumps({"queue_id": queue_id, "txn_id": event.txn_id, "risk_tier": screen.tier.value}),
                    now, None, 0, None,
                ))
            queued += 1
        insert_many_or_ignore(
            con, "investigation_queue",
            ("queue_id", "txn_id", "network_id", "risk_tier", "status", "created_at", "updated_at", "priority", "attempt_count"),
            q_rows, "queue_id",
        )
        insert_many_or_ignore(
            con, "flagged_transactions",
            ("txn_id", "sender_id", "receiver_id", "amount", "corridor", "ts", "risk_score",
             "primary_pattern", "fraud_scenario", "currency", "purpose", "source_of_funds",
             "risk_tier", "network_id", "workflow_state"),
            flag_rows, "txn_id",
        )
        if out_rows:
            insert_many_or_ignore(
                con, "outbox_events",
                ("outbox_id", "event_type", "payload", "created_at", "published_at", "attempts", "last_error"),
                out_rows, "outbox_id",
            )
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
