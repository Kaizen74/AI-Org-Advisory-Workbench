"""Access-allowlist management — /api/v1/access (D13). Owner-only."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import get_session
from ..services import access_service
from .auth_dep import require_owner

router = APIRouter(prefix="/api/v1/access", tags=["access"])


class AccessUserBody(BaseModel):
    email: str
    passcode: str
    is_owner: bool = False


@router.get("")
async def list_users(_owner: dict = Depends(require_owner), session: AsyncSession = Depends(get_session)):
    return {"users": await access_service.list_users(session)}


@router.post("", status_code=201)
async def add_user(body: AccessUserBody, owner: dict = Depends(require_owner),
                   session: AsyncSession = Depends(get_session)):
    user = await access_service.add_user(session, body.email, body.passcode, is_owner=body.is_owner)
    return {"email": user.email, "is_owner": user.is_owner}


@router.delete("/{email}")
async def remove_user(email: str, owner: dict = Depends(require_owner),
                      session: AsyncSession = Depends(get_session)):
    # Guard: don't let the last owner remove themselves into lockout.
    if email.strip().lower() == owner.get("email"):
        users = await access_service.list_users(session)
        if sum(1 for u in users if u["is_owner"]) <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the only owner")
    ok = await access_service.remove_user(session, email)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return {"removed": email}
