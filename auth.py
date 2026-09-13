"""Password login plus role-based authorization.

Console users come from credentials.json / CORRIDOR_WATCH_USERS.
Header fallback stays available only for local automated tests.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import Cookie, Depends, Header, HTTPException

ROLES = {"analyst", "fiu_lead", "mrm_auditor"}
PERMISSIONS = {
    "analyst": {
        "alerts:read", "investigate", "decision:write", "sof:run", "memory:read",
        "debate:run", "document:verify", "counterfactual:run", "sar:draft", "audit:case",
        "command:read", "corridors:read", "patterns:read", "simulate:read",
        "intelligence:read",
        "workflow:review", "workflow:refer",
    },
    "fiu_lead": {
        "alerts:read", "investigate", "decision:write", "decision:high_risk",
        "sof:run", "memory:read", "debate:run", "document:verify", "counterfactual:run",
        "sar:draft", "audit:case", "audit:recent",
        "command:read", "corridors:read", "patterns:read", "patterns:write",
        "simulate:read", "simulate:run",
        "intelligence:read", "intelligence:write",
        "workflow:review", "workflow:escalate", "workflow:close",
    },
    "mrm_auditor": {
        "alerts:read", "investigate", "memory:read", "debate:run", "document:verify",
        "counterfactual:run", "sar:draft", "audit:case", "audit:recent", "mrm:read",
        "redteam:run", "redteam:reset", "rules:mine",
        "command:read", "corridors:read", "patterns:read",
        "simulate:read", "simulate:run",
        "intelligence:read",
        "workflow:audit",
    },
}

ROLE_LABELS = {
    "analyst": "Compliance Analyst",
    "fiu_lead": "FIU Team Lead",
    "mrm_auditor": "MRM Auditor",
}

SESSION_TTL_SECONDS = 12 * 60 * 60
ROOT = Path(__file__).resolve().parent
COOKIE_NAME = "cw_session"


@dataclass(frozen=True)
class AuthContext:
    analyst_id: str
    role: str
    mode: str
    display_name: str = ""
    permissions: tuple[str, ...] = ()


def _production_keys() -> dict[str, dict[str, str]]:
    raw = os.getenv("CORRIDOR_WATCH_API_KEYS", "")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError("CORRIDOR_WATCH_API_KEYS must be valid JSON") from exc


def _load_credentials() -> dict:
    raw = os.getenv("CORRIDOR_WATCH_USERS", "")
    if raw:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"users": data}
    path = Path(os.getenv("CORRIDOR_WATCH_USERS_FILE") or "")
    if not path.is_file():
        path = ROOT / "credentials.json"
    if not path.is_file():
        path = ROOT / "credentials.example.json"
    if not path.is_file():
        return {"auth_secret": "", "users": []}
    return json.loads(path.read_text())


def list_users() -> list[dict]:
    data = _load_credentials()
    users = data.get("users") or []
    out = []
    for user in users:
        role = user.get("role")
        if role not in ROLES or not user.get("username"):
            continue
        out.append(user)
    return out


def _auth_secret() -> str:
    env = os.getenv("CORRIDOR_WATCH_AUTH_SECRET", "")
    if env:
        return env
    return str(_load_credentials().get("auth_secret") or "corridor-watch-dev-secret")


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    pad = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + pad)


def issue_session(user: dict) -> str:
    payload = {
        "analyst_id": user.get("analyst_id") or user["username"],
        "username": user["username"],
        "role": user["role"],
        "display_name": user.get("display_name") or ROLE_LABELS.get(user["role"], user["role"]),
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
    }
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _b64url(hmac.new(_auth_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def parse_session(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None
    body, _, sig = token.partition(".")
    expected = _b64url(hmac.new(_auth_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(_b64url_decode(body))
    except (json.JSONDecodeError, ValueError):
        return None
    if int(payload.get("exp") or 0) < int(time.time()):
        return None
    if payload.get("role") not in ROLES:
        return None
    return payload


def authenticate(username: str, password: str) -> dict:
    if not username or not password:
        raise HTTPException(401, "username and password required")
    for user in list_users():
        if user["username"] != username:
            continue
        if not hmac.compare_digest(str(user.get("password") or ""), password):
            raise HTTPException(401, "invalid username or password")
        return user
    raise HTTPException(401, "invalid username or password")


def _from_payload(payload: dict, mode: str) -> AuthContext:
    role = payload["role"]
    return AuthContext(
        analyst_id=payload.get("analyst_id") or payload.get("username") or "unknown",
        role=role,
        mode=mode,
        display_name=payload.get("display_name") or ROLE_LABELS.get(role, role),
        permissions=tuple(sorted(PERMISSIONS.get(role, set()))),
    )


def get_auth_context(
    authorization: str | None = Header(default=None),
    x_analyst_id: str | None = Header(default=None, alias="X-Analyst-ID"),
    x_analyst_role: str | None = Header(default=None, alias="X-Analyst-Role"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    cw_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
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
        return _from_payload({"analyst_id": analyst_id, "role": role, "display_name": ROLE_LABELS.get(role, role)}, "api_key")

    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    token = token or cw_session
    payload = parse_session(token)
    if payload:
        return _from_payload(payload, "password")

    allow_headers = os.getenv("ENVIRONMENT", "local") != "gcp"
    if allow_headers and (x_analyst_role or x_analyst_id):
        role = x_analyst_role or "analyst"
        if role not in ROLES:
            raise HTTPException(403, f"unsupported role: {role}")
        return _from_payload(
            {
                "analyst_id": x_analyst_id or "analyst_demo",
                "role": role,
                "display_name": ROLE_LABELS.get(role, role),
            },
            "header",
        )

    raise HTTPException(401, "sign in required")


def require(permission: str):
    def dependency(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if permission not in PERMISSIONS.get(ctx.role, set()):
            raise HTTPException(403, f"role '{ctx.role}' lacks permission '{permission}'")
        return ctx
    return dependency


def public_me(ctx: AuthContext) -> dict:
    return {
        "analyst_id": ctx.analyst_id,
        "role": ctx.role,
        "display_name": ctx.display_name or ROLE_LABELS.get(ctx.role, ctx.role),
        "permissions": sorted(PERMISSIONS.get(ctx.role, set())),
        "mode": ctx.mode,
    }
