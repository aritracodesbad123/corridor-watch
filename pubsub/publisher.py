"""Publish transaction events to Pub/Sub or a local HTTP ingest endpoint."""
from __future__ import annotations

import json
import time
from typing import Iterable

from config import get_settings
from pubsub.schemas import TransactionEvent

_wiring_cache: dict = {"ts": 0.0, "value": None}


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


def publish_gcp(events: Iterable[TransactionEvent]) -> int:
    """Batched Pub/Sub publish. Requires GOOGLE_CLOUD_PROJECT and ADC."""
    settings = get_settings()
    if not settings.google_cloud_project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set")
    from google.cloud import pubsub_v1

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(settings.google_cloud_project, settings.transaction_topic)
    futures = []
    for ev in events:
        data = json.dumps(ev.model_dump()).encode("utf-8")
        futures.append(publisher.publish(topic_path, data, txn_id=ev.txn_id))
    for fut in futures:
        fut.result(timeout=30)
    return len(futures)


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
