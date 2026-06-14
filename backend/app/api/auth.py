"""Auth router — /api/v1/auth (D13). Public: login. Authenticated: me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import get_session
from ..services import access_service, audit_service
from ..services.token_service import make_token
from .auth_dep import require_auth

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: str
    passcode: str


@router.post("/login")
async def login(body: LoginBody, session: AsyncSession = Depends(get_session)):
    user = await access_service.verify(session, body.email, body.passcode)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or passcode")
    await audit_service.record(session, None, "login", {"email": user.email})
    return {
        "token": make_token(user.email, user.is_owner),
        "email": user.email,
        "owner": user.is_owner,
    }


@router.get("/me")
async def me(user: dict = Depends(require_auth)):
    return {"email": user.get("email"), "owner": user.get("owner", False)}
