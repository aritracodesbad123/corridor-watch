"""Environment-driven configuration. Never commit credentials."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw not in (None, "") else default


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    google_cloud_project: str
    region: str
    transaction_topic: str
    investigation_topic: str
    pubsub_push_subscription: str
    gemini_model: str
    ingest_token: str
    risk_threshold_low: float
    risk_threshold_medium: float
    risk_threshold_high: float
    graph_max_hops: int
    graph_lookback_minutes: int
    graph_lookahead_minutes: int
    max_investigation_size: int
    max_investigation_edges: int

    @property
    def is_postgres(self) -> bool:
        url = (self.database_url or "").lower()
        return url.startswith("postgres://") or url.startswith("postgresql://")

    @property
    def dialect(self) -> str:
        return "postgres" if self.is_postgres else "sqlite"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("ENVIRONMENT", "local"),
        database_url=os.getenv("DATABASE_URL", ""),
        google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        region=os.getenv("REGION", "asia-southeast1"),
        transaction_topic=os.getenv("TRANSACTION_TOPIC", "corridor-transactions"),
        investigation_topic=os.getenv("INVESTIGATION_TOPIC", "corridor-investigations"),
        pubsub_push_subscription=os.getenv("PUBSUB_PUSH_SUBSCRIPTION", "corridor-transactions-push"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
        ingest_token=os.getenv("CORRIDOR_WATCH_INGEST_TOKEN", ""),
        risk_threshold_low=_float("RISK_THRESHOLD_LOW", 25.0),
        risk_threshold_medium=_float("RISK_THRESHOLD_MEDIUM", 40.0),
        risk_threshold_high=_float("RISK_THRESHOLD_HIGH", 75.0),
        graph_max_hops=_int("GRAPH_MAX_HOPS", 3),
        graph_lookback_minutes=_int("GRAPH_LOOKBACK_MINUTES", 1440),
        graph_lookahead_minutes=_int("GRAPH_LOOKAHEAD_MINUTES", 120),
        max_investigation_size=_int("MAX_INVESTIGATION_SIZE", 200),
        max_investigation_edges=_int("MAX_INVESTIGATION_EDGES", 400),
    )


def reset_settings_cache() -> None:
    get_settings.cache_clear()
