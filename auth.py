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


HIGH_RISK_DECISIONS = {"hold_payment", "escalate_fiu", "freeze_account"}
HIGH_RISK_WORKFLOW = {"escalate"}


@dataclass(frozen=True)
class AuthContext:
    analyst_id: str
    role: str
    mode: str
    display_name: str = ""
    permissions: tuple[str, ...] = ()
    mfa: bool = False


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


def oidc_enabled() -> bool:
    return bool(os.getenv("OIDC_ISSUER"))


def _mfa_from_claims(claims: dict) -> bool:
    if claims.get("mfa") is True:
        return True
    amr = claims.get("amr") or []
    if isinstance(amr, str):
        amr = [amr]
    return any(str(item).lower() in {"mfa", "otp", "hwk", "pwd+mfa"} for item in amr)


def _verify_hs256_jwt(token: str, secret: str, issuer: str, audience: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(401, "invalid oidc token")
    header_b64, payload_b64, sig = parts
    expected = _b64url(hmac.new(secret.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(401, "invalid oidc token")
    try:
        header = json.loads(_b64url_decode(header_b64))
        claims = json.loads(_b64url_decode(payload_b64))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(401, "invalid oidc token") from exc
    if header.get("alg") != "HS256":
        raise HTTPException(401, "unsupported oidc alg")
    if issuer and claims.get("iss") != issuer:
        raise HTTPException(401, "oidc issuer mismatch")
    aud = claims.get("aud")
    if audience and aud not in (audience, [audience]):
        raise HTTPException(401, "oidc audience mismatch")
    if int(claims.get("exp") or 0) < int(time.time()):
        raise HTTPException(401, "oidc token expired")
    return claims


def verify_oidc_token(token: str) -> dict:
    issuer = os.getenv("OIDC_ISSUER", "")
    audience = os.getenv("OIDC_AUDIENCE", "")
    if "accounts.google.com" in issuer:
        try:
            from google.auth.transport import requests as greq
            from google.oauth2 import id_token
        except ImportError as exc:
            raise HTTPException(401, "google-auth is required for Google OIDC") from exc
        try:
            return id_token.verify_oauth2_token(token, greq.Request(), audience=audience or None)
        except Exception as exc:
            raise HTTPException(401, "invalid oidc token") from exc
    secret = os.getenv("OIDC_CLIENT_SECRET") or ""
    if not secret:
        raise HTTPException(401, "OIDC_CLIENT_SECRET is required for this issuer")
    return _verify_hs256_jwt(token, secret, issuer, audience)


def _from_oidc(token: str) -> AuthContext:
    claims = verify_oidc_token(token)
    email = str(claims.get("email") or claims.get("sub") or "").lower()
    mapping = {}
    raw_map = os.getenv("OIDC_EMAIL_ROLES") or ""
    if raw_map:
        try:
            mapping = {str(k).lower(): v for k, v in json.loads(raw_map).items()}
        except json.JSONDecodeError as exc:
            raise HTTPException(500, "OIDC_EMAIL_ROLES must be valid JSON") from exc
    role = mapping.get(email)
    analyst_id = email or "oidc-user"
    if not role:
        for user in list_users():
            aliases = {
                str(user.get("email") or "").lower(),
                str(user.get("username") or "").lower(),
            }
            if email and email in aliases:
                role = user["role"]
                analyst_id = user.get("analyst_id") or user["username"]
                break
    if not role:
        claimed = claims.get("role") or ""
        if claimed in ROLES:
            role = claimed
    if role not in ROLES:
        raise HTTPException(403, "oidc identity is not mapped to a console role")
    return AuthContext(
        analyst_id=analyst_id,
        role=role,
        mode="oidc",
        display_name=str(claims.get("name") or ROLE_LABELS.get(role, role)),
        permissions=tuple(sorted(PERMISSIONS.get(role, set()))),
        mfa=_mfa_from_claims(claims),
    )


def assert_step_up(ctx: AuthContext, action: str) -> None:
    """High-risk actions need an MFA-backed SSO session when OIDC is configured."""
    risky = action in HIGH_RISK_DECISIONS or action in HIGH_RISK_WORKFLOW
    if not risky or not oidc_enabled():
        return
    if os.getenv("OIDC_REQUIRE_MFA", "1").lower() not in {"1", "true", "yes"}:
        return
    if ctx.mode != "oidc" or not ctx.mfa:
        raise HTTPException(403, "MFA-backed SSO session required for this action")


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

    bearer = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization.split(" ", 1)[1].strip()
    payload = parse_session(bearer or cw_session)
    if payload:
        return _from_payload(payload, "password")
    if bearer and oidc_enabled():
        return _from_oidc(bearer)

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
        "mfa": ctx.mfa,
        "oidc": oidc_enabled(),
    }
