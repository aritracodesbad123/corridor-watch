"""Publish generated events through the local ingest function (no network)."""
from __future__ import annotations

from pubsub.ingestion import ingest_batch
from pubsub.schemas import TransactionEvent


def publish_in_process(events: list[TransactionEvent], *, source: str = "loadgen") -> dict:
    return ingest_batch([(ev, ev.txn_id) for ev in events], source=source)
