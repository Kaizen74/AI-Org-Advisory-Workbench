"""Settings router — /api/v1/settings (pre-P7, D11/D12).

Manages LLM provider/key/models + local-LLM endpoint + brand (palette + logo) through the UI.
Secrets are masked on read. Non-AI; no API key required to read/write settings.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import get_session
from ..services import settings_service as ss
from ..services.claude_service import claude_service

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

BRAND_DIR = Path(__file__).resolve().parents[2] / "uploads" / "brand"
_ALLOWED_LOGO = {".png", ".jpg", ".jpeg", ".gif"}


@router.get("")
async def get_settings(session: AsyncSession = Depends(get_session)):
    await ss.load_from_db(session)
    return ss.public_view()


@router.put("")
async def update_settings(updates: dict = Body(...), session: AsyncSession = Depends(get_session)):
    return await ss.update_settings(session, updates)


@router.post("/brand-logo")
async def upload_brand_logo(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_LOGO:
        raise HTTPException(status_code=400, detail=f"Unsupported logo type: {ext or 'none'}")
    os.makedirs(BRAND_DIR, exist_ok=True)
    path = BRAND_DIR / f"logo{ext}"
    path.write_bytes(await file.read())
    # Clear any other-extension logos so only one is active.
    for other in _ALLOWED_LOGO:
        if other != ext:
            stale = BRAND_DIR / f"logo{other}"
            if stale.exists():
                stale.unlink()
    await ss.update_settings(session, {"brand_logo_path": str(path)})
    return {"brand_logo_path": str(path)}


@router.get("/brand-logo")
async def get_brand_logo():
    path = ss.get("brand_logo_path")
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="No brand logo set")
    return FileResponse(path, filename=Path(path).name)


@router.post("/test-llm")
async def test_llm(session: AsyncSession = Depends(get_session)):
    """Make a tiny live call under the current provider to verify connectivity (used by the UI)."""
    await ss.load_from_db(session)
    if not claude_service.has_api_key:
        raise HTTPException(status_code=400, detail="No provider configured (key or local URL).")
    try:
        text = claude_service.complete(
            model=ss.get("model_extract"),
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        )
        return {"ok": True, "provider": ss.llm_provider(), "sample": (text or "")[:80]}
    except Exception as e:  # noqa: BLE001 - surface connection errors to the UI
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")
