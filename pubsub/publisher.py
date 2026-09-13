"""Publish transaction events to Pub/Sub or a local HTTP ingest endpoint."""
from __future__ import annotations

import json
import time
from typing import Iterable

from config import get_settings
from pubsub.schemas import TransactionEvent

_wiring_cache: dict = {"ts": 0.0, "value": None}
_PUBLISHER = None


def use_gcp_pubsub() -> bool:
    settings = get_settings()
    return settings.environment == "gcp" and bool(settings.google_cloud_project)


def publish_local(events: Iterable[TransactionEvent], *, ingest_url: str, token: str = "") -> dict:
    """Batch HTTP publish — used by the local load generator."""
    import urllib.request

    payload = {
        "messages": [
            {"message_id": ev.txn_id, "transaction": ev.model_dump()}
            for ev in events
        ]
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Ingest-Token"] = token
    req = urllib.request.Request(ingest_url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _publisher():
    global _PUBLISHER
    if _PUBLISHER is None:
        from google.cloud import pubsub_v1
        _PUBLISHER = pubsub_v1.PublisherClient()
    return _PUBLISHER


def publish_gcp(events: Iterable[TransactionEvent]) -> int:
    """Batched Pub/Sub publish. Requires GOOGLE_CLOUD_PROJECT and ADC."""
    settings = get_settings()
    if not settings.google_cloud_project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set")
    publisher = _publisher()
    topic_path = publisher.topic_path(settings.google_cloud_project, settings.transaction_topic)
    futures = []
    for ev in events:
        data = json.dumps(ev.model_dump()).encode("utf-8")
        futures.append(publisher.publish(topic_path, data, txn_id=ev.txn_id))
    for fut in futures:
        fut.result(timeout=30)
    return len(futures)


def notify_investigation(payload: dict) -> None:
    """Best-effort fan-out. Durable work stays in PostgreSQL investigation_queue.

    Never blocks ingest. Do not treat this as a second consumer pipeline.
    """
    import os

    if os.getenv("CW_SKIP_INVESTIGATION_NOTIFY", "").lower() in {"1", "true", "yes"}:
        return
    settings = get_settings()
    if settings.environment != "gcp" or not settings.google_cloud_project:
        return
    try:
        publisher = _publisher()
        topic_path = publisher.topic_path(settings.google_cloud_project, settings.investigation_topic)
        publisher.publish(topic_path, json.dumps(payload).encode("utf-8"))
    except Exception:
        return


def describe_wiring() -> dict:
    """Best-effort topic/subscription status. Cached briefly so the console stays snappy."""
    settings = get_settings()
    now = time.time()
    cached = _wiring_cache.get("value")
    if cached is not None and now - float(_wiring_cache.get("ts") or 0) < 20:
        return cached
    payload = {
        "wired": False,
        "project": settings.google_cloud_project or None,
        "topic": settings.transaction_topic,
        "investigation_topic": settings.investigation_topic,
        "investigation_path": "pubsub_transactions → Cloud Run → PostgreSQL investigation_queue",
        "investigation_topic_role": "optional fan-out signal; not the consumer pipeline",
        "subscription": settings.pubsub_push_subscription,
        "push_endpoint": None,
        "backlog": None,
        "error": None,
    }
    if settings.environment != "gcp" or not settings.google_cloud_project:
        _wiring_cache.update(ts=now, value=payload)
        return payload
    try:
        from google.cloud import pubsub_v1
        publisher = pubsub_v1.PublisherClient()
        subscriber = pubsub_v1.SubscriberClient()
        topic_path = publisher.topic_path(settings.google_cloud_project, settings.transaction_topic)
        publisher.get_topic(request={"topic": topic_path})
        sub_path = subscriber.subscription_path(
            settings.google_cloud_project, settings.pubsub_push_subscription
        )
        sub = subscriber.get_subscription(request={"subscription": sub_path})
        payload["wired"] = True
        payload["push_endpoint"] = sub.push_config.push_endpoint or None
    except Exception as exc:
        payload["error"] = str(exc)
    _wiring_cache.update(ts=now, value=payload)
    return payload
