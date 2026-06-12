"""FastAPI application entrypoint.

Per Build Spec A3 Rule 5, changes to this file in later phases are limited to `include_router`
lines and startup config — never edits to existing routes of completed phases.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import diagnostics, engagements, task_intel
from .config import settings

app = FastAPI(
    title="OrgAI Advisory Workbench API",
    version="0.0.0",  # bumps as phases ship
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
