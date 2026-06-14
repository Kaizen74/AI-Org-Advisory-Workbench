"""Deliverable visual themes (Phase 6).

Modern-minimalist default (DECISIONS.md D10): near-black ink, muted-teal accent, light rules, white
ground, generous whitespace, light-weight large titles. Centralized so a SATS-branded theme drops in
later without touching generator logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

SATS_LOGO_PATH = str(
    Path(__file__).resolve().parents[1] / "resources" / "brand" / "sats_logo.png"
)


@dataclass(frozen=True)
class Theme:
    name: str
    ink: str        # primary text (hex, no '#')
    muted: str      # secondary text
    accent: str     # single restrained accent
    rule: str       # thin divider lines
    ground: str     # background
    title_font: str
    body_font: str
    extras: Dict[str, str] = field(default_factory=dict)


MINIMAL = Theme(
    name="minimal",
    ink="1F2933",
    muted="6B7280",
    accent="2F6F6A",      # muted teal
    rule="E5E7EB",
    ground="FFFFFF",
    title_font="Calibri Light",
    body_font="Calibri",
)

# SATS brand theme — extracted from the SATS Corporate Presentation Template (Dec 2024):
# brand red EE2536, deep purple 50284F, light grey D5D7D7, Arial. Logo committed as a resource.
SATS = Theme(
    name="SATS",
    ink="1F2933",
    muted="6B7280",
    accent="EE2536",      # SATS brand red
    rule="D5D7D7",        # SATS light grey
    ground="FFFFFF",
    title_font="Arial",
    body_font="Arial",
    extras={"logo_path": SATS_LOGO_PATH, "secondary": "50284F"},
)

THEMES = {"minimal": MINIMAL, "sats": SATS}


def theme_from_settings() -> Theme:
    """Build a Theme from the UI-managed brand settings (D12), falling back to MINIMAL tokens.

    `brand_palette` may supply any of ink/accent/muted/rule/ground (hex, no '#'); a `brand_logo_path`
    is carried in `extras['logo_path']` so the title slide can render the logo.
    """
    from . import settings_service  # local import avoids any import-order coupling

    palette = settings_service.brand_palette()
    logo = settings_service.get("brand_logo_path")
    name = settings_service.get("brand_name") or "brand"

    def pick(key: str, default: str) -> str:
        val = str(palette.get(key, "") or "").lstrip("#").strip()
        return val or default

    return Theme(
        name=name,
        ink=pick("ink", MINIMAL.ink),
        muted=pick("muted", MINIMAL.muted),
        accent=pick("accent", MINIMAL.accent),
        rule=pick("rule", MINIMAL.rule),
        ground=pick("ground", MINIMAL.ground),
        title_font=MINIMAL.title_font,
        body_font=MINIMAL.body_font,
        extras={"logo_path": logo} if logo else {},
    )


def get_theme(name: str | None) -> Theme:
    key = (name or "minimal").lower()
    if key == "brand":
        return theme_from_settings()
    return THEMES.get(key, MINIMAL)
