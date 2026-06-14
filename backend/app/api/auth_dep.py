"""Auth dependencies (D13). Protect routers with `Depends(require_auth)` / `Depends(require_owner)`.

Tests override `require_auth` so existing suites run as an authenticated user.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException

from ..services.token_service import verify_token


def require_auth(authorization: Optional[str] = Header(default=None)) -> dict:
    """Return the token payload for a valid Bearer token, else 401."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(authorization.split(" ", 1)[1].strip())
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


def require_owner(user: dict = Depends(require_auth)) -> dict:
    if not user.get("owner"):
        raise HTTPException(status_code=403, detail="Owner access required")
    return user
