"""Request correlation IDs. No OpenTelemetry SDK — W3C / Cloud Trace headers only."""
from __future__ import annotations

import contextvars
import uuid

_current: contextvars.ContextVar[dict] = contextvars.ContextVar("cw_trace", default=None)


def current() -> dict:
    return dict(_current.get() or {})


def bind(**fields) -> dict:
    ctx = current()
    ctx.update({k: v for k, v in fields.items() if v not in (None, "")})
    _current.set(ctx)
    return ctx


def start_request(headers) -> dict:
    incoming = ""
    if headers is not None:
        incoming = (
            headers.get("x-trace-id")
            or _from_traceparent(headers.get("traceparent") or "")
            or _from_cloud_trace(headers.get("x-cloud-trace-context") or "")
        )
    return bind(trace_id=incoming or uuid.uuid4().hex, span_id=uuid.uuid4().hex[:16])


def _from_traceparent(value: str) -> str:
    parts = value.split("-")
    if len(parts) >= 3 and len(parts[1]) == 32:
        return parts[1]
    return ""


def _from_cloud_trace(value: str) -> str:
    return value.split("/", 1)[0].strip() if value else ""
