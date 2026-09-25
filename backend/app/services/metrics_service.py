"""Metrics calculator service.

PORTED in Phase 1 from the legacy v1 app (`legacy/backend/app/services/metrics_service.py`). The
formulas are carried over unchanged; the only adaptation is the **ID-keyed graph** (PRD M1): the
graph is built from `positions` keyed on `employee_key`/`manager_key` instead of name. On the
provided PAX CSV this reproduces the legacy v1 output exactly (DECISIONS.md D9).

`calculate_all_metrics()` returns a nested dict; the diagnostics service flattens the headline
figures into typed `metric_values` rows for persistence (Build Spec B1/B2).
"""
from __future__ import annotations

import statistics
from typing import Dict, List, Optional

import networkx as nx

TOP_SENTINELS = {"Top of Org", "N/A", "", "nan", "None"}


class MetricsCalculator:
    """Calculate org metrics with the validated v1 formulas, on an ID-keyed graph."""

    def __init__(self, positions: List[Dict], grade_order: Optional[Dict[str, int]] = None):
        """positions: list of dicts with employee_key, manager_key, salary, level, grade,
        display_name. grade_order: map grade -> numeric rank (1 = highest)."""
        self.positions = positions
        self.grade_order = grade_order or {}
        self.graph = self._build_graph()

    def _build_graph(self) -> nx.DiGraph:
        g = nx.DiGraph()
        keys = {p["employee_key"] for p in self.positions}
        for p in self.positions:
            g.add_node(p["employee_key"], **p)
        for p in self.positions:
            mk = p.get("manager_key")
            if mk and mk in keys:
                g.add_edge(mk, p["employee_key"])
        return g

    def calculate_all_metrics(self) -> Dict:
        return {
            "total_employees": self._total_employees(),
            "manager_stats": self._manager_statistics(),
            "span_of_control": self._span_of_control(),
            "cost_analysis": self._cost_analysis(),
            "grade_gap_analysis": self._grade_gap_analysis(),
            "layer_analysis": self._layer_analysis(),
            "health_indicators": self._health_indicators(),
        }

    def _total_employees(self) -> int:
        return len(self.graph.nodes())

    def _manager_statistics(self) -> Dict:
        total = len(self.graph.nodes())
        if total == 0:
            return {"total_managers": 0, "total_ics": 0, "manager_ratio_pct": 0.0, "ic_ratio_pct": 0.0}
        managers = [n for n in self.graph.nodes() if self.graph.out_degree(n) > 0]
        manager_count = len(managers)
        ic_count = total - manager_count
        return {
            "total_managers": manager_count,
            "total_ics": ic_count,
            "manager_ratio_pct": round(manager_count / total * 100, 1),
            "ic_ratio_pct": round(ic_count / total * 100, 1),
        }

    def _span_of_control(self) -> Dict:
        spans: List[int] = []
        by_manager: Dict[str, int] = {}
        distribution = {"Narrow (<5)": 0, "Optimal (5-10)": 0, "Wide (>10)": 0}
        for node in self.graph.nodes():
            span = self.graph.out_degree(node)
            if span > 0:
                spans.append(span)
                by_manager[node] = span
                if span < 5:
                    distribution["Narrow (<5)"] += 1
                elif span <= 10:
                    distribution["Optimal (5-10)"] += 1
                else:
                    distribution["Wide (>10)"] += 1
        if not spans:
            return {
                "average_span": 0.0, "median_span": 0.0, "min_span": 0, "max_span": 0,
                "distribution": distribution, "distribution_pct": {}, "by_manager": {},
            }
        total_managers = len(spans)
        return {
            "average_span": round(statistics.mean(spans), 2),
            "median_span": round(statistics.median(spans), 2),
            "min_span": min(spans),
            "max_span": max(spans),
            "distribution": distribution,
            "distribution_pct": {k: round(v / total_managers * 100, 1) for k, v in distribution.items()},
            "by_manager": by_manager,
        }

    def _cost_analysis(self) -> Dict:
        total_cost = sum(self.graph.nodes[n].get("salary", 0) for n in self.graph.nodes())
        total_emp = len(self.graph.nodes())
        by_level: Dict[int, Dict] = {}
        for node in self.graph.nodes():
            level = self.graph.nodes[node].get("level", 0)
            salary = self.graph.nodes[node].get("salary", 0)
            by_level.setdefault(level, {"count": 0, "total_cost": 0})
            by_level[level]["count"] += 1
            by_level[level]["total_cost"] += salary
        by_grade: Dict[str, Dict] = {}
        for node in self.graph.nodes():
            grade = self.graph.nodes[node].get("grade", "Unknown")
            salary = self.graph.nodes[node].get("salary", 0)
            by_grade.setdefault(grade, {"count": 0, "total_cost": 0})
            by_grade[grade]["count"] += 1
            by_grade[grade]["total_cost"] += salary
        return {
            "total_cost": round(total_cost, 0),
            "average_cost_per_employee": round(total_cost / total_emp, 0) if total_emp > 0 else 0,
            "by_level": by_level,
            "by_grade": by_grade,
        }

    def _grade_gap_analysis(self) -> Dict:
        if not self.grade_order:
            return {
                "average_grade_gap": 0.0, "total_comparisons": 0, "gaps": [],
                "note": "No grade order configured",
            }
        gaps: List[int] = []
        gap_details: List[Dict] = []
        for mgr in self.graph.nodes():
            mgr_grade = self.graph.nodes[mgr].get("grade")
            if mgr_grade not in self.grade_order:
                continue
            for sub in self.graph.successors(mgr):
                sub_grade = self.graph.nodes[sub].get("grade")
                if sub_grade in self.grade_order:
                    gap = self.grade_order[sub_grade] - self.grade_order[mgr_grade]
                    gaps.append(gap)
                    gap_details.append({
                        "manager": mgr, "manager_grade": mgr_grade,
                        "subordinate": sub, "subordinate_grade": sub_grade, "gap": gap,
                    })
        unusual_gaps = [g for g in gap_details if g["gap"] < 1 or g["gap"] > 4]
        return {
            "average_grade_gap": round(statistics.mean(gaps), 2) if gaps else 0.0,
            "min_gap": min(gaps) if gaps else 0,
            "max_gap": max(gaps) if gaps else 0,
            "total_comparisons": len(gaps),
            "unusual_gaps": unusual_gaps[:10],
        }

    def _layer_analysis(self) -> Dict:
        levels = [self.graph.nodes[n].get("level", 0) for n in self.graph.nodes()]
        if not levels:
            return {"total_layers": 0, "by_level": {}}
        by_level: Dict[int, Dict] = {}
        for node in self.graph.nodes():
            level = self.graph.nodes[node].get("level", 0)
            by_level.setdefault(level, {"count": 0})
            by_level[level]["count"] += 1
        return {"total_layers": max(levels), "by_level": by_level}

    def _health_indicators(self) -> Dict:
        span = self._span_of_control()
        mgr = self._manager_statistics()
        warnings: List[str] = []
        recommendations: List[str] = []
        if span["average_span"] < 5:
            warnings.append(f"Low avg span ({span['average_span']}) - consider consolidation")
            recommendations.append("Increase span of control by combining teams or reducing management layers")
        narrow_pct = span["distribution_pct"].get("Narrow (<5)", 0)
        if narrow_pct > 60:
            warnings.append(f"{narrow_pct}% managers have narrow spans (<5 reports)")
            recommendations.append("Review managers with 1-2 direct reports for potential consolidation")
        if mgr["manager_ratio_pct"] > 30:
            warnings.append(f"High manager ratio ({mgr['manager_ratio_pct']}%) - potential overhead")
            recommendations.append("Benchmark against industry standards (typically 15-25% managers)")
        if span["max_span"] > 15:
            warnings.append(f"Some managers have very wide spans (max: {span['max_span']})")
            recommendations.append("Consider adding team leads or splitting large teams")
        health_score = max(0, 100 - len(warnings) * 15)
        return {
            "health_score": health_score,
            "health_grade": self._score_to_grade(health_score),
            "warnings": warnings,
            "recommendations": recommendations,
            "is_healthy": len(warnings) <= 2,
        }

    @staticmethod
    def _score_to_grade(score: int) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"
