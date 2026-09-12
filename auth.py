"""Lightweight role-based authorization for the POC.

Demo mode intentionally accepts X-Analyst-* headers so the local console remains
self-contained. Production mode requires an API key mapped to an analyst + role.
This is not a replacement for an IdP/Entra integration; it makes the authorization
boundary explicit and testable while preserving the demo path.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

ROLES = {"analyst", "fiu_lead", "mrm_auditor"}
PERMISSIONS = {
    "analyst": {
        "alerts:read", "investigate", "decision:write", "sof:run", "memory:read",
        "debate:run", "document:verify", "counterfactual:run", "sar:draft", "audit:case",
    },
    "fiu_lead": {
        "alerts:read", "investigate", "decision:write", "decision:high_risk",
        "sof:run", "memory:read", "debate:run", "document:verify", "counterfactual:run",
        "sar:draft", "audit:case", "audit:recent",
    },
    "mrm_auditor": {
        "alerts:read", "investigate", "memory:read", "debate:run", "document:verify",
        "counterfactual:run", "sar:draft", "audit:case", "audit:recent", "mrm:read",
        "redteam:run", "redteam:reset", "rules:mine",
    },
}

@dataclass(frozen=True)
class AuthContext:
    analyst_id: str
    role: str
    mode: str


def _production_keys() -> dict[str, dict[str, str]]:
    raw = os.getenv("CORRIDOR_WATCH_API_KEYS", "")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError("CORRIDOR_WATCH_API_KEYS must be valid JSON") from exc


def get_auth_context(
    x_analyst_id: str | None = Header(default=None, alias="X-Analyst-ID"),
    x_analyst_role: str | None = Header(default=None, alias="X-Analyst-Role"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> AuthContext:
    keys = _production_keys()
    if keys:
        record = keys.get(x_api_key or "")
        if not record:
            raise HTTPException(401, "valid X-API-Key required")
        role = record.get("role", "")
        analyst_id = record.get("analyst_id", "")
        if role not in ROLES or not analyst_id:
            raise HTTPException(403, "invalid API key role mapping")
        return AuthContext(analyst_id=analyst_id, role=role, mode="api_key")

    # Explicit demo fallback. This keeps the challenge app runnable without an IdP.
    role = x_analyst_role or "analyst"
    if role not in ROLES:
        raise HTTPException(403, f"unsupported role: {role}")
    return AuthContext(analyst_id=x_analyst_id or "analyst_demo", role=role, mode="demo_header")


def require(permission: str):
    def dependency(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if permission not in PERMISSIONS.get(ctx.role, set()):
            raise HTTPException(403, f"role '{ctx.role}' lacks permission '{permission}'")
        return ctx
    return dependency
