"""Access allowlist service (D13).

Manages who may log in: salted PBKDF2 passcode hashes, owner flag, bootstrap from the `ACCESS_USERS`
env var on first run. No new dependencies (stdlib hashlib/secrets).
"""
from __future__ import annotations

import hashlib
import secrets
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import AccessUser

_PBKDF2_ROUNDS = 200_000


def _hash(passcode: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", passcode.encode("utf-8"), salt.encode("utf-8"),
                               _PBKDF2_ROUNDS).hex()


def _norm(email: str) -> str:
    return (email or "").strip().lower()


async def count_users(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(AccessUser)) or 0)


async def add_user(session: AsyncSession, email: str, passcode: str, is_owner: bool = False) -> AccessUser:
    email = _norm(email)
    salt = secrets.token_hex(16)
    existing = await session.get(AccessUser, email)
    if existing is None:
        existing = AccessUser(email=email)
        session.add(existing)
    existing.salt = salt
    existing.passcode_hash = _hash(passcode, salt)
    existing.is_owner = is_owner
    await session.flush()
    return existing


async def remove_user(session: AsyncSession, email: str) -> bool:
    user = await session.get(AccessUser, _norm(email))
    if user is None:
        return False
    await session.delete(user)
    await session.flush()
    return True


async def verify(session: AsyncSession, email: str, passcode: str) -> Optional[AccessUser]:
    user = await session.get(AccessUser, _norm(email))
    if user is None:
        return None
    candidate = _hash(passcode, user.salt)
    if not secrets.compare_digest(candidate, user.passcode_hash):
        return None
    return user


async def list_users(session: AsyncSession) -> List[dict]:
    rows = await session.scalars(select(AccessUser).order_by(AccessUser.email))
    return [{"email": u.email, "is_owner": u.is_owner, "created_at": str(u.created_at)} for u in rows]


async def bootstrap(session: AsyncSession) -> int:
    """Seed owners from the ACCESS_USERS env var if the allowlist is empty. Returns count added."""
    if await count_users(session) > 0 or not settings.ACCESS_USERS.strip():
        return 0
    added = 0
    for pair in settings.ACCESS_USERS.split(","):
        if ":" not in pair:
            continue
        email, passcode = pair.split(":", 1)
        if email.strip() and passcode.strip():
            await add_user(session, email.strip(), passcode.strip(), is_owner=True)
            added += 1
    return added
