"""FastAPI application entrypoint.

Per Build Spec A3 Rule 5, changes to this file in later phases are limited to `include_router`
lines and startup config — never edits to existing routes of completed phases.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    audit,
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
from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On boot, hydrate the settings cache from the DB so the LLM provider/key/brand are active (D11)."""
    from .models import async_session
    from .services import settings_service

    try:
        async with async_session() as session:
            await settings_service.load_from_db(session)
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


# ── Routers (one `include_router` line per module as phases ship) ────────────
app.include_router(engagements.router)
app.include_router(diagnostics.router)
app.include_router(task_intel.router)
app.include_router(validation.router)
app.include_router(scenarios.router)
app.include_router(workflows.router)
app.include_router(transition.router)
app.include_router(deliverables.router)
app.include_router(settings_api.router)
app.include_router(audit.router)
