"""Inbound transaction event schema for Pub/Sub and HTTP ingest."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class TransactionEvent(BaseModel):
    txn_id: str = Field(min_length=1, max_length=64)
    timestamp: str
    sender_account_id: str = Field(min_length=1, max_length=64)
    receiver_account_id: str = Field(min_length=1, max_length=64)
    amount: float = Field(gt=0, le=50_000_000)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    origin_country: str = Field(default="", max_length=8)
    destination_country: str = Field(default="", max_length=8)
    origin_bank_id: str = Field(default="", max_length=32)
    destination_bank_id: str = Field(default="", max_length=32)
    channel: str = Field(default="remittance", max_length=32)
    beneficiary_id: str = Field(default="", max_length=64)
    device_id: str = Field(default="", max_length=64)
    session_id: str = Field(default="", max_length=64)
    purpose: str = Field(default="", max_length=200)
    source_of_funds: str = Field(default="", max_length=200)
    fraud_scenario: str = Field(default="normal", max_length=64)
    scenario_id: str = Field(default="", max_length=64)
    account_age_days: int | None = Field(default=None, ge=0, le=20000)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp must be ISO-8601") from exc
        return value

    @property
    def corridor(self) -> str:
        src = self.origin_country or "??"
        dst = self.destination_country or "??"
        return f"{src}->{dst}"

    def as_row(self) -> dict:
        return {
            "txn_id": self.txn_id,
            "sender_id": self.sender_account_id,
            "receiver_id": self.receiver_account_id,
            "amount": self.amount,
            "currency": self.currency,
            "corridor": self.corridor,
            "ts": self.timestamp,
            "device_id": self.device_id or None,
            "session_id": self.session_id or None,
            "beneficiary_id": self.beneficiary_id or None,
            "purpose": self.purpose,
            "source_of_funds": self.source_of_funds,
            "fraud_scenario": self.fraud_scenario,
            "origin_country": self.origin_country,
            "destination_country": self.destination_country,
            "origin_bank_id": self.origin_bank_id,
            "destination_bank_id": self.destination_bank_id,
            "channel": self.channel,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
