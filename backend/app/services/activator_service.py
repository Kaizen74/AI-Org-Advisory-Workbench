"""Kates-Kesler activator pre-screen (Phase 1, PRD M1).

Maps the deterministic structural metrics to the Five Activators as **leading-indicator flags**
(e.g. layer bloat -> Activator 1; coordination/narrow-span fragmentation -> Activator 2). This is a
transparent heuristic screen, NOT the full Observable Outcomes framework (that is a manual-input
pack, PRD §9 out of scope). Thresholds are module constants so they are easy to tune; every flag is
tagged `basis="heuristic-leading-indicator"`. The exact activator labels are pending Eric's
confirmation (see LATEST.md) — the slots and triggers are stable regardless.

Pure + deterministic (tested per Part A Rule 6).
"""
from __future__ import annotations

from typing import Dict

# Heuristic thresholds (leading indicators, tunable).
MAX_HEALTHY_LAYERS = 7
NARROW_SPAN_FRAGMENTATION_PCT = 50.0
MIN_HEALTHY_AVG_SPAN = 5.0
HIGH_MANAGER_RATIO_PCT = 30.0
MIN_HEALTHY_SCORE = 70

CAVEAT = (
    "Heuristic leading-indicator pre-screen from structural metrics only. Confirm against the "
    "Observable Outcomes pack and validate with the consultant before client use; activator labels "
    "pending confirmation."
)


def compute_activator_screen(metrics: Dict) -> Dict:
    """Return Five-Activator leading-indicator flags from a full metrics payload."""
    span = metrics.get("span_of_control", {})
    mgr = metrics.get("manager_stats", {})
    layers = metrics.get("layer_analysis", {})
    health = metrics.get("health_indicators", {})

    total_layers = layers.get("total_layers", 0)
    narrow_pct = span.get("distribution_pct", {}).get("Narrow (<5)", 0)
    avg_span = span.get("average_span", 0)
    manager_ratio = mgr.get("manager_ratio_pct", 0)
    health_score = health.get("health_score", 100)

    flags = [
        _flag(
            1, "Structure & Layers",
            triggered=total_layers > MAX_HEALTHY_LAYERS,
            signal="organizational_layers", value=total_layers, threshold=MAX_HEALTHY_LAYERS,
            rationale="Layer bloat dilutes accountability and slows decisions.",
        ),
        _flag(
            2, "Lateral Connection & Coordination",
            triggered=narrow_pct > NARROW_SPAN_FRAGMENTATION_PCT,
            signal="narrow_span_pct", value=narrow_pct, threshold=NARROW_SPAN_FRAGMENTATION_PCT,
            rationale="Many narrow-span managers signal fragmentation and coordination gaps.",
        ),
        _flag(
            3, "Spans of Control",
            triggered=avg_span < MIN_HEALTHY_AVG_SPAN,
            signal="average_span", value=avg_span, threshold=MIN_HEALTHY_AVG_SPAN,
            rationale="Low average span indicates over-supervision and excess management cost.",
        ),
        _flag(
            4, "Management Overhead",
            triggered=manager_ratio > HIGH_MANAGER_RATIO_PCT,
            signal="manager_ratio_pct", value=manager_ratio, threshold=HIGH_MANAGER_RATIO_PCT,
            rationale="High manager ratio suggests structural overhead vs. value-adding roles.",
        ),
        _flag(
            5, "Structural Health",
            triggered=health_score < MIN_HEALTHY_SCORE,
            signal="health_score", value=health_score, threshold=MIN_HEALTHY_SCORE,
            rationale="Composite structural health below threshold; review flagged warnings.",
        ),
    ]
    return {
        "flags": flags,
        "triggered_count": sum(1 for f in flags if f["triggered"]),
        "caveat": CAVEAT,
    }


def _flag(activator: int, name: str, *, triggered: bool, signal: str, value, threshold, rationale) -> Dict:
    return {
        "activator": activator,
        "name": name,
        "triggered": bool(triggered),
        "signal_metric": signal,
        "value": value,
        "threshold": threshold,
        "rationale": rationale,
        "basis": "heuristic-leading-indicator",
    }
