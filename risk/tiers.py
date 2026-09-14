"""Configurable risk tiers. Gemini is never invoked here."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from config import get_settings
from db import connect


class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ScreenResult:
    score: float
    tier: RiskTier
    signals: list[str] = field(default_factory=list)


def assign_tier(score: float) -> RiskTier:
    settings = get_settings()
    if score >= settings.risk_threshold_high:
        return RiskTier.CRITICAL
    if score >= settings.risk_threshold_medium:
        return RiskTier.HIGH
    if score >= settings.risk_threshold_low:
        return RiskTier.MEDIUM
    return RiskTier.LOW


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def cheap_screen(txn: dict, con=None, *, velocity: bool = True) -> ScreenResult:
    """Fast, bounded screening — no graph traversal, no Gemini."""
    signals: list[str] = []
    score = 0.0
    amount = float(txn.get("amount") or 0)
    corridor = txn.get("corridor") or ""
    sender = txn.get("sender_account_id") or txn.get("sender_id") or ""
    ts = _parse_ts(txn.get("timestamp") or txn.get("ts"))

    if amount >= 8000:
        score += 25
        signals.append("high_value")
    elif amount >= 4000:
        score += 12
        signals.append("elevated_value")

    if "->" in corridor:
        src, dst = [p.strip() for p in corridor.split("->", 1)]
        if src and dst and src != dst:
            score += 8
            signals.append("cross_border")
        if src in {"??", ""} or dst in {"??", ""}:
            score += 10
            signals.append("unknown_corridor_leg")

    account_age = txn.get("account_age_days")
    if account_age is not None and int(account_age) <= 7:
        score += 18
        signals.append("new_account")

    if sender and velocity:
        score += _recent_velocity(sender, ts, con)

    score = min(score, 100.0)
    return ScreenResult(score=round(score, 1), tier=assign_tier(score), signals=signals)


def _recent_velocity(sender_id: str, ts: datetime | None, con=None) -> float:
    """Count sender activity in a 60-minute window. Cheap SQL, not a graph walk."""
    if ts is None:
        return 0.0
    window_start = (ts - timedelta(minutes=60)).isoformat()
    window_end = ts.isoformat()
    own = con is None
    try:
        if own:
            con = connect()
        row = con.execute(
            "SELECT COUNT(*) AS c FROM transactions WHERE sender_id=? AND ts>=? AND ts<=?",
            (sender_id, window_start, window_end),
        ).fetchone()
        if own:
            con.close()
        count = int(row["c"] if row is not None else 0)
    except Exception:
        if own and con is not None:
            try:
                con.close()
            except Exception:
                pass
        return 0.0
    if count >= 8:
        return 20.0
    if count >= 4:
        return 10.0
    return 0.0
