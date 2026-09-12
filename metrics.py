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
        }


METRICS = MetricsRegistry()
