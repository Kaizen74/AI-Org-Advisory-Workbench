"""Stateless login tokens (D13) — HMAC-signed, stdlib only (no JWT dependency).

Token = base64url(payload_json) + "." + base64url(hmac_sha256(payload, AUTH_SECRET)). Payload carries
the email, owner flag and an expiry. `verify_token` returns the payload or None (bad sig / expired).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from ..config import settings


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(payload_b64: str, secret: Optional[str] = None) -> str:
    key = (secret or settings.AUTH_SECRET).encode("utf-8")
    return _b64e(hmac.new(key, payload_b64.encode("ascii"), hashlib.sha256).digest())


def make_token(email: str, is_owner: bool, ttl_hours: Optional[int] = None,
               secret: Optional[str] = None) -> str:
    ttl = ttl_hours if ttl_hours is not None else settings.AUTH_TOKEN_TTL_HOURS
    payload = {"email": email, "owner": bool(is_owner), "exp": int(time.time()) + ttl * 3600}
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{payload_b64}.{_sign(payload_b64, secret)}"


def verify_token(token: str, secret: Optional[str] = None) -> Optional[dict]:
    try:
        payload_b64, sig = token.split(".", 1)
    except ValueError:
        return None
    expected = _sign(payload_b64, secret)
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(_b64d(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload
