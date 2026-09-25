"""FastAPI application entrypoint.

Per Build Spec A3 Rule 5, changes to this file in later phases are limited to `include_router`
lines and startup config — never edits to existing routes of completed phases.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    access,
    audit,
    auth,
    deliverables,
    diagnostics,
    engagements,
    scenarios,
    settings as settings_api,
    task_intel,
    transition,
    validation,
    workflows,
)
from .api.auth_dep import require_auth
from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On boot, hydrate the settings cache from the DB so the LLM provider/key/brand are active (D11)."""
    from .models import async_session
    from .services import settings_service

    from .services import access_service

    try:
        async with async_session() as session:
            await settings_service.load_from_db(session)
            await access_service.bootstrap(session)  # seed the allowlist from ACCESS_USERS (D13)
            await session.commit()
    except Exception:  # noqa: BLE001 - a fresh/unmigrated DB must not block startup
        pass
    yield


app = FastAPI(
    title="OrgAI Advisory Workbench API",
    version="0.0.0",  # bumps as phases ship
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Liveness probe — proves the app boots. No API key required (Build Spec B2)."""
    return {"status": "ok"}


# ── Routers ──────────────────────────────────────────────────────────────────
# Public: auth (login). All feature routers are gated by require_auth (D13 — private app).
app.include_router(auth.router)
app.include_router(access.router)  # routes are owner-only (require_owner)

_protected = [Depends(require_auth)]
app.include_router(engagements.router, dependencies=_protected)
app.include_router(diagnostics.router, dependencies=_protected)
app.include_router(task_intel.router, dependencies=_protected)
app.include_router(validation.router, dependencies=_protected)
app.include_router(scenarios.router, dependencies=_protected)
app.include_router(workflows.router, dependencies=_protected)
app.include_router(transition.router, dependencies=_protected)
app.include_router(deliverables.router, dependencies=_protected)
app.include_router(settings_api.router, dependencies=_protected)
app.include_router(audit.router, dependencies=_protected)
