"""App settings service (pre-P7, D11/D12).

DB-backed key/value settings with an in-memory cache so the (sync) `claude_service` can read the
current LLM config without an async DB round-trip. The Settings API writes both DB + cache. Secrets
are masked when surfaced over the API.

Settings covered:
  * LLM: `llm_provider` (anthropic|local), `anthropic_api_key`, `model_extract`, `model_synth`,
    `local_base_url`, `local_model`, `local_api_key`.
  * Brand: `brand_name`, `brand_palette` (JSON ink/accent/muted/rule/ground), `brand_logo_path`.
"""
from __future__ import annotations

import json
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings as env
from ..models import AppSetting

SECRET_KEYS = {"anthropic_api_key", "local_api_key"}

DEFAULTS: Dict[str, str] = {
    "llm_provider": "anthropic",
    "anthropic_api_key": env.ANTHROPIC_API_KEY or "",
    "model_extract": env.MODEL_EXTRACT,
    "model_synth": env.MODEL_SYNTH,
    "local_base_url": "http://localhost:11434/v1",
    "local_model": "llama3.1",
    "local_api_key": "",
    "brand_name": "",
    "brand_palette": "",      # JSON string: {ink,accent,muted,rule,ground}
    "brand_logo_path": "",
}

# Process-wide cache (env-seeded). Updated on every DB write and on startup load.
_cache: Dict[str, str] = dict(DEFAULTS)


def current() -> Dict[str, str]:
    """Sync snapshot of all settings (for claude_service / deliverable_theme)."""
    return dict(_cache)


def get(key: str, default: str = "") -> str:
    return _cache.get(key, default)


def reset_cache_for_tests() -> None:
    _cache.clear()
    _cache.update(DEFAULTS)


async def load_from_db(session: AsyncSession) -> Dict[str, str]:
    """Populate the cache from persisted rows (call at startup / before reads that must be fresh)."""
    rows = await session.scalars(select(AppSetting))
    for r in rows:
        if r.key in DEFAULTS:
            _cache[r.key] = r.value or ""
    return current()


async def update_settings(session: AsyncSession, updates: Dict[str, str]) -> Dict:
    """Upsert known settings to DB + cache. Ignores unknown keys. Returns the masked public view."""
    for key, value in updates.items():
        if key not in DEFAULTS:
            continue
        sval = "" if value is None else str(value)
        row = await session.get(AppSetting, key)
        if row is None:
            session.add(AppSetting(key=key, value=sval))
        else:
            row.value = sval
        _cache[key] = sval
    await session.flush()
    return public_view()


def public_view() -> Dict:
    """Non-secret settings as-is; secrets surfaced only as presence + last-4."""
    out: Dict = {}
    for key, value in _cache.items():
        if key in SECRET_KEYS:
            out[f"{key}_set"] = bool(value)
            out[f"{key}_last4"] = value[-4:] if value else ""
        else:
            out[key] = value
    return out


# ── Convenience accessors used by claude_service / deliverable_theme ─────────
def llm_provider() -> str:
    return (_cache.get("llm_provider") or "anthropic").lower()


def anthropic_key() -> str:
    return _cache.get("anthropic_api_key") or ""


def local_config() -> Dict[str, str]:
    return {
        "base_url": _cache.get("local_base_url") or "",
        "model": _cache.get("local_model") or "",
        "api_key": _cache.get("local_api_key") or "",
    }


def brand_palette() -> Dict[str, str]:
    raw = _cache.get("brand_palette") or ""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}
