"""Live GCP signals for the command center. Failures return nulls, never invented counts."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from config import get_settings

_CACHE: dict = {"ts": 0.0, "value": None}


def _adc_token() -> str | None:
    try:
        import google.auth
        from google.auth.transport.requests import Request
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if not creds.valid:
            creds.refresh(Request())
        return creds.token
    except Exception:
        return None


def _metric_latest(project: str, token: str, metric_type: str, extra_filter: str = "") -> float | None:
    import json
    import urllib.parse
    import urllib.request

    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=5)
    filt = f'metric.type="{metric_type}"'
    if extra_filter:
        filt = f"{filt} AND {extra_filter}"
    params = urllib.parse.urlencode({
        "filter": filt,
        "interval.startTime": start.isoformat().replace("+00:00", "Z"),
        "interval.endTime": end.isoformat().replace("+00:00", "Z"),
        "view": "FULL",
        "pageSize": 20,
    })
    req = urllib.request.Request(
        f"https://monitoring.googleapis.com/v3/projects/{project}/timeSeries?{params}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    series = payload.get("timeSeries") or []
    latest = None
    total = 0.0
    found = False
    for entry in series:
        points = entry.get("points") or []
        if not points:
            continue
        value = (points[0].get("value") or {})
        parsed = None
        for key in ("int64Value", "doubleValue"):
            if value.get(key) is not None:
                parsed = float(value[key])
                break
        if parsed is None:
            continue
        found = True
        total += parsed
        if latest is None:
            latest = parsed
    if not found:
        return None
    if metric_type.endswith("instance_count"):
        return total
    return latest


def platform_signals() -> dict:
    now = time.time()
    cached = _CACHE.get("value")
    if cached is not None and now - float(_CACHE.get("ts") or 0) < 45:
        return cached
    settings = get_settings()
    out = {
        "pubsub_backlog": None,
        "cloud_run_instances": None,
        "source": "unavailable",
    }
    if settings.environment != "gcp" or not settings.google_cloud_project:
        out["source"] = "local"
        _CACHE.update(ts=now, value=out)
        return out
    token = _adc_token()
    if not token:
        out["source"] = "no_adc"
        _CACHE.update(ts=now, value=out)
        return out
    project = settings.google_cloud_project
    backlog = _metric_latest(
        project,
        token,
        "pubsub.googleapis.com/subscription/num_undelivered_messages",
        f'resource.labels.subscription_id="{settings.pubsub_push_subscription}"',
    )
    instances = _metric_latest(
        project,
        token,
        "run.googleapis.com/container/instance_count",
        'resource.labels.service_name="corridor-watch"',
    )
    out["pubsub_backlog"] = int(backlog) if backlog is not None else None
    out["cloud_run_instances"] = int(instances) if instances is not None else None
    out["source"] = "cloud_monitoring"
    _CACHE.update(ts=now, value=out)
    return out
