"""Diagnostics service.

Bridges the pure metrics engine to typed persistence: `flatten_metric_values()` turns the nested
`calculate_all_metrics()` payload into a flat list of typed `metric_values` rows (metric_code,
scope, scope_key, value, unit) so metrics are queryable/trendable rather than a JSON blob
(PRD M1 / Build Spec B1). The flattening is pure and deterministic (tested per Part A Rule 6); the
async `compute_and_persist()` helper writes the rows under a dataset.
"""
from __future__ import annotations

from typing import Dict, List

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import MetricValue, Position
from ..parsers.csv_parser import OrgCSVParser  # noqa: F401  (re-exported convenience)
from .metrics_service import MetricsCalculator

# (metric_code, unit, dotted path into the metrics payload)
_ORG_METRICS = [
    ("total_employees", "count", ("total_employees",)),
    ("total_managers", "count", ("manager_stats", "total_managers")),
    ("total_ics", "count", ("manager_stats", "total_ics")),
    ("manager_ratio_pct", "percent", ("manager_stats", "manager_ratio_pct")),
    ("average_span", "ratio", ("span_of_control", "average_span")),
    ("median_span", "ratio", ("span_of_control", "median_span")),
    ("max_span", "count", ("span_of_control", "max_span")),
    ("total_cost", "currency", ("cost_analysis", "total_cost")),
    ("average_cost_per_employee", "currency", ("cost_analysis", "average_cost_per_employee")),
    ("organizational_layers", "count", ("layer_analysis", "total_layers")),
    ("health_score", "score", ("health_indicators", "health_score")),
]


def _dig(payload: Dict, path: tuple):
    node = payload
    for key in path:
        node = node[key]
    return node


def flatten_metric_values(metrics: Dict) -> List[Dict]:
    """Flatten the metrics payload into typed org-scope metric rows. Pure + deterministic."""
    rows: List[Dict] = []
    for metric_code, unit, path in _ORG_METRICS:
        rows.append(
            {
                "metric_code": metric_code,
                "scope": "org",
                "scope_key": None,
                "value": float(_dig(metrics, path)),
                "unit": unit,
            }
        )
    return rows


def positions_to_dicts(positions: List[Position]) -> List[Dict]:
    """Adapt ORM Position rows to the dicts the metrics engine consumes."""
    return [
        {
            "employee_key": p.employee_key,
            "manager_key": p.manager_key,
            "display_name": p.display_name,
            "job_title": p.job_title,
            "grade": p.grade,
            "level": p.level or 0,
            "department": p.department,
            "salary": p.salary or 0.0,
            "work_activities": p.work_activities or "",
        }
        for p in positions
    ]


async def compute_and_persist(session: AsyncSession, dataset_id: str, positions: List[Position]) -> Dict:
    """Compute metrics for a dataset's positions and (re)write its typed metric_values rows.

    Returns the full nested metrics payload. Idempotent: existing rows for the dataset are cleared
    first so recompute is clean.
    """
    metrics = MetricsCalculator(positions_to_dicts(positions)).calculate_all_metrics()

    await session.execute(delete(MetricValue).where(MetricValue.dataset_id == dataset_id))
    for row in flatten_metric_values(metrics):
        session.add(MetricValue(dataset_id=dataset_id, **row))
    await session.flush()
    return metrics
