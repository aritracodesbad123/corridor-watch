"""In-process application metrics. Cloud Monitoring can scrape /api/metrics."""
from __future__ import annotations

import threading
import time
from collections import defaultdict


class _Reservoir:
    def __init__(self, cap: int = 2048):
        self.cap = cap
        self.values: list[float] = []
        self.lock = threading.Lock()

    def add(self, value: float) -> None:
        with self.lock:
            if len(self.values) < self.cap:
                self.values.append(value)
            else:
                self.values.pop(0)
                self.values.append(value)

    def percentile(self, p: float) -> float:
        with self.lock:
            if not self.values:
                return 0.0
            ordered = sorted(self.values)
        rank = min(len(ordered) - 1, max(0, int(round((p / 100.0) * (len(ordered) - 1)))))
        return round(ordered[rank], 4)


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._started = time.time()
        self._ingest_times: list[float] = []
        self.ingestion_latency = _Reservoir()
        self.gemini_latency = _Reservoir()
        self.investigation_latency = _Reservoir()
        self.stages: dict[str, _Reservoir] = {
            "ingest_decode": _Reservoir(),
            "ingest_validate": _Reservoir(),
            "ingest_idempotency": _Reservoir(),
            "ingest_transaction_write": _Reservoir(),
            "ingest_queue_write": _Reservoir(),
            "ingest_publish": _Reservoir(),
            "ingest_total": _Reservoir(),
            "db_pool_wait": _Reservoir(),
            "db_connection_checkout": _Reservoir(),
        }

    def observe(self, name: str, ms: float) -> None:
        bucket = self.stages.get(name)
        if bucket is not None:
            bucket.add(ms)

    def inc(self, name: str, n: int = 1) -> None:
        now = time.time()
        with self._lock:
            self._counters[name] += n
            if name == "transactions_received_total":
                for _ in range(max(1, n)):
                    self._ingest_times.append(now)
                cutoff = now - 60.0
                self._ingest_times = [t for t in self._ingest_times if t >= cutoff]

    def live_tps(self) -> float:
        now = time.time()
        with self._lock:
            cutoff = now - 60.0
            self._ingest_times = [t for t in self._ingest_times if t >= cutoff]
            count = len(self._ingest_times)
        span = 60.0 if count else 1.0
        if self._ingest_times:
            span = max(1.0, now - self._ingest_times[0])
        return round(count / span, 2)

    def snapshot(self) -> dict:
        with self._lock:
            counters = dict(self._counters)
        elapsed = max(time.time() - self._started, 0.001)
        received = counters.get("transactions_received_total", 0)
        return {
            "uptime_seconds": round(elapsed, 2),
            "live_tps": self.live_tps(),
            "session_tps": round(received / elapsed, 2),
            "counters": counters,
            "ingestion_latency_ms": {
                "p50": self.ingestion_latency.percentile(50),
                "p95": self.ingestion_latency.percentile(95),
                "p99": self.ingestion_latency.percentile(99),
            },
            "gemini_latency_ms": {
                "p50": self.gemini_latency.percentile(50),
                "p95": self.gemini_latency.percentile(95),
                "p99": self.gemini_latency.percentile(99),
            },
            "investigation_latency_ms": {
                "p50": self.investigation_latency.percentile(50),
                "p95": self.investigation_latency.percentile(95),
                "p99": self.investigation_latency.percentile(99),
            },
            "ingest_stages_ms": {
                name: {"p50": r.percentile(50), "p95": r.percentile(95), "p99": r.percentile(99)}
                for name, r in self.stages.items()
            },
            "slos": self.slo_status(),
        }

    def slo_status(self) -> dict:
        """Compare measured samples to promised targets. Targets, not claims of compliance."""
        ingest_p95 = self.ingestion_latency.percentile(95)
        gemini_p95 = self.gemini_latency.percentile(95)
        inv_p95 = self.investigation_latency.percentile(95)
        counters = dict(self._counters)
        received = counters.get("transactions_received_total", 0)
        failed = counters.get("transactions_failed_total", 0)
        dupes = counters.get("transactions_duplicate_total", 0)
        http_n = counters.get("http_requests_total", 0)
        http_5xx = counters.get("http_5xx_total", 0)
        completed = counters.get("investigations_completed_total", 0)
        return {
            "ingestion_accept_within_2s": {
                "target": "99.9% of valid events accepted within 2s",
                "p95_ms": ingest_p95,
                "status": "ok" if ingest_p95 <= 2000 or received == 0 else "breach",
            },
            "investigation_within_10s": {
                "target": "99% of deterministic investigations complete within 10s",
                "p95_ms": inv_p95,
                "status": "ok" if inv_p95 <= 10000 or completed == 0 else "breach",
            },
            "ai_fail_safe_within_30s": {
                "target": "99% of Gemini calls complete or fail safely within 30s",
                "p95_ms": gemini_p95,
                "status": "ok" if gemini_p95 <= 30000 else "breach",
            },
            "api_availability": {
                "target": "99.9% monthly API availability",
                "session_5xx": http_5xx,
                "session_requests": http_n,
                "status": "ok" if http_n == 0 or (http_5xx / http_n) <= 0.001 else "breach",
                "note": "session rate only — not a monthly measurement",
            },
            "ingest_error_rate": {
                "failed": failed,
                "received": received,
                "duplicates": dupes,
            },
        }

    def evaluate_alerts(
        self,
        *,
        queue: dict | None = None,
        pool: dict | None = None,
        pubsub_backlog: float | None = None,
    ) -> list[dict]:
        """Threshold checks on measured samples. Empty list means nothing is firing."""
        counters = dict(self._counters)
        firing: list[dict] = []
        if pubsub_backlog is not None and pubsub_backlog > 1000:
            firing.append({"id": "pubsub_lag", "severity": "warning", "detail": f"backlog={int(pubsub_backlog)}"})
        util = (pool or {}).get("utilization")
        if util is not None and util > 0.8:
            firing.append({"id": "db_pool", "severity": "warning", "detail": f"utilization={util}"})
        reqs = counters.get("http_requests_total", 0)
        err5 = counters.get("http_5xx_total", 0)
        if reqs and (err5 / reqs) > 0.01:
            firing.append({"id": "http_5xx", "severity": "critical", "detail": f"{err5}/{reqs}"})
        started = counters.get("investigations_started_total", 0)
        failed_inv = counters.get("investigations_failed_total", 0)
        if started and (failed_inv / started) > 0.005:
            firing.append({"id": "investigation_failures", "severity": "warning", "detail": f"{failed_inv}/{started}"})
        dlq = int((queue or {}).get("DEAD_LETTER") or 0)
        if dlq > 0:
            firing.append({"id": "dlq", "severity": "critical", "detail": f"dead_letter={dlq}"})
        gemini_n = counters.get("gemini_requests_total", 0)
        gemini_fail = counters.get("gemini_failures_total", 0)
        if gemini_n and (gemini_fail / gemini_n) > 0.05:
            firing.append({"id": "gemini_errors", "severity": "warning", "detail": f"{gemini_fail}/{gemini_n}"})
        return firing


METRICS = MetricsRegistry()
