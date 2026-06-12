"""Scenario service (Phase 4, Build Spec M3/B2).

Manages scenarios + ordered design moves, computes deltas against the baseline dataset's persisted
`metric_values` (NOT a re-parsed CSV), compares up to N scenarios, and enforces present/lock/fork:
a PRESENTED scenario is immutable; editing forks a new DRAFT (`parent_scenario_id`).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Dataset, DesignMove, MetricValue, Position, Scenario, ScenarioMetric
from .diagnostics_service import flatten_metric_values, positions_to_dicts
from .metrics_service import MetricsCalculator
from .scenario_engine import apply_moves


class ScenarioLocked(Exception):
    """Raised when editing a PRESENTED (immutable) scenario."""


# ── CRUD ─────────────────────────────────────────────────────────────────────
async def create_scenario(
    session: AsyncSession, *, engagement_id: str, dataset_id: str, name: str
) -> Optional[Scenario]:
    if await session.get(Dataset, dataset_id) is None:
        return None
    scenario = Scenario(engagement_id=engagement_id, dataset_id=dataset_id, name=name, status="DRAFT")
    session.add(scenario)
    await session.flush()
    return scenario


async def list_scenarios(session: AsyncSession, engagement_id: Optional[str] = None) -> List[Scenario]:
    stmt = select(Scenario)
    if engagement_id:
        stmt = stmt.where(Scenario.engagement_id == engagement_id)
    return list(await session.scalars(stmt.order_by(Scenario.created_at)))


async def get_scenario(session: AsyncSession, scenario_id: str) -> Optional[Scenario]:
    return await session.get(Scenario, scenario_id)


async def _moves_as_dicts(session: AsyncSession, scenario_id: str) -> List[Dict]:
    moves = await session.scalars(
        select(DesignMove).where(DesignMove.scenario_id == scenario_id).order_by(DesignMove.seq)
    )
    return [{"move_type": m.move_type, "params": m.params or {}} for m in moves]


# ── Moves (locked once PRESENTED) ────────────────────────────────────────────
async def add_move(
    session: AsyncSession, scenario_id: str, *, move_type: str, params: Optional[dict],
    rationale: Optional[str] = None, activator_tag: Optional[int] = None,
) -> Optional[DesignMove]:
    scenario = await session.get(Scenario, scenario_id)
    if scenario is None:
        return None
    if scenario.status == "PRESENTED":
        raise ScenarioLocked()
    next_seq = (await session.scalar(
        select(func.max(DesignMove.seq)).where(DesignMove.scenario_id == scenario_id)
    ) or 0) + 1
    move = DesignMove(scenario_id=scenario_id, seq=next_seq, move_type=move_type, params=params,
                      rationale=rationale, activator_tag=activator_tag)
    session.add(move)
    await session.flush()
    return move


async def remove_move(session: AsyncSession, scenario_id: str, seq: int) -> bool:
    scenario = await session.get(Scenario, scenario_id)
    if scenario is None:
        return False
    if scenario.status == "PRESENTED":
        raise ScenarioLocked()
    result = await session.execute(
        delete(DesignMove).where(DesignMove.scenario_id == scenario_id, DesignMove.seq == seq)
    )
    await session.flush()
    return result.rowcount > 0


# ── Delta vs persisted baseline metric_values ────────────────────────────────
async def _baseline_metrics(session: AsyncSession, dataset_id: str, positions) -> Dict[str, float]:
    """Headline baseline metrics from persisted metric_values; fall back to computing if absent."""
    rows = list(await session.scalars(
        select(MetricValue).where(MetricValue.dataset_id == dataset_id)
    ))
    if rows:
        return {r.metric_code: r.value for r in rows}
    computed = MetricsCalculator(positions_to_dicts(positions)).calculate_all_metrics()
    return {r["metric_code"]: r["value"] for r in flatten_metric_values(computed)}


async def compute_delta(session: AsyncSession, scenario_id: str) -> Optional[Dict]:
    scenario = await session.get(Scenario, scenario_id)
    if scenario is None:
        return None
    positions = list(await session.scalars(
        select(Position).where(Position.dataset_id == scenario.dataset_id)
    ))
    baseline = await _baseline_metrics(session, scenario.dataset_id, positions)

    moves = await _moves_as_dicts(session, scenario_id)
    scenario_positions = apply_moves(positions_to_dicts(positions), moves)
    scn_metrics = {
        r["metric_code"]: r["value"]
        for r in flatten_metric_values(
            MetricsCalculator(scenario_positions).calculate_all_metrics()
        )
    }

    delta = {code: round(scn_metrics[code] - baseline.get(code, 0), 4) for code in scn_metrics}

    # Persist scenario_metrics (idempotent).
    await session.execute(delete(ScenarioMetric).where(ScenarioMetric.scenario_id == scenario_id))
    for code, value in scn_metrics.items():
        session.add(ScenarioMetric(scenario_id=scenario_id, metric_code=code, value=value,
                                   delta_vs_baseline=delta[code]))
    await session.flush()

    return {"scenario_id": scenario_id, "name": scenario.name, "status": scenario.status,
            "move_count": len(moves), "baseline": baseline, "scenario": scn_metrics, "delta": delta}


async def compare(session: AsyncSession, ids: List[str]) -> Dict:
    """Side-by-side deltas for up to N scenarios (the workshop comparison view)."""
    results = []
    for sid in ids:
        d = await compute_delta(session, sid)
        if d is not None:
            results.append(d)
    return {"scenarios": results}


# ── Present / lock / fork ────────────────────────────────────────────────────
async def present(session: AsyncSession, scenario_id: str) -> Optional[Scenario]:
    scenario = await session.get(Scenario, scenario_id)
    if scenario is None:
        return None
    scenario.status = "PRESENTED"
    await session.flush()
    return scenario


async def fork(session: AsyncSession, scenario_id: str, new_name: Optional[str] = None) -> Optional[Scenario]:
    parent = await session.get(Scenario, scenario_id)
    if parent is None:
        return None
    child = Scenario(engagement_id=parent.engagement_id, dataset_id=parent.dataset_id,
                     name=new_name or f"{parent.name} (fork)", status="DRAFT",
                     parent_scenario_id=parent.id)
    session.add(child)
    await session.flush()
    for m in await session.scalars(
        select(DesignMove).where(DesignMove.scenario_id == scenario_id).order_by(DesignMove.seq)
    ):
        session.add(DesignMove(scenario_id=child.id, seq=m.seq, move_type=m.move_type,
                               params=m.params, rationale=m.rationale, activator_tag=m.activator_tag))
    await session.flush()
    return child
