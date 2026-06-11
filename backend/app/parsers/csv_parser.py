"""CSV parser for organizational structure data.

PORTED in Phase 1 from the legacy v1 app (`legacy/backend/app/parsers/csv_parser.py`) with the
**one breaking fix mandated by PRD M1 / Build Spec B0**: the org graph is keyed on **Employee ID**
(with a generated surrogate key when absent), NEVER on name. Consequences:
  * Two people with the same name remain distinct nodes (the v1 name-keyed graph silently collapsed
    them, losing positions). Name collisions instead raise a validation warning listing duplicates.
  * The "Line Manager" column still holds a manager *name*, so manager linkage is resolved through a
    name→key map; an ambiguous (duplicated) manager name links to the first match and warns.

Encoding detection, required-column validation, and cycle/root/orphan checks are carried over.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx
import pandas as pd

# Manager-cell values that mean "no manager / top of org".
TOP_SENTINELS = {"Top of Org", "N/A", "", "nan", "None"}


class OrgCSVParser:
    """Parse a CSV org structure into ID-keyed positions, a graph, warnings and metadata."""

    REQUIRED_COLUMNS = ["Name", "Job Title", "Grade", "Level", "Line Manager"]
    OPTIONAL_COLUMNS = ["Department", "Employee ID", "Salary", "Work Activities", "Job Description"]

    def __init__(self, csv_source):
        """csv_source: a file path (str/Path) or a file-like object."""
        self.csv_source = csv_source
        self.df: Optional[pd.DataFrame] = None
        self.graph: Optional[nx.DiGraph] = None

    # ── public API ───────────────────────────────────────────────────────────
    def parse(self) -> Dict[str, Any]:
        try:
            self.df = self._read_csv_with_encoding()
        except Exception as e:  # noqa: BLE001 - mirror legacy: never raise to caller
            return self._empty(f"Failed to read CSV: {e}")

        self.df = self.df.dropna(how="all")

        column_errors = self._validate_columns()
        if column_errors:
            return self._empty(*column_errors)

        self.df = self._clean_data()
        positions, warnings = self._build_positions()
        self.graph = self._build_graph(positions)

        warnings += self._detect_issues()
        metadata = self._calculate_metadata(positions)

        return {
            "positions": positions,
            "graph": self.graph,
            "validation_warnings": warnings[:20],
            "metadata": metadata,
        }

    # ── reading & cleaning (carried over) ────────────────────────────────────
    def _read_csv_with_encoding(self) -> pd.DataFrame:
        encodings = ["utf-8", "cp1252", "latin-1", "iso-8859-1"]
        if isinstance(self.csv_source, (str, Path)):
            last_error: Optional[Exception] = None
            for enc in encodings:
                try:
                    return pd.read_csv(self.csv_source, encoding=enc)
                except UnicodeDecodeError as e:
                    last_error = e
            raise last_error or Exception("Failed to decode CSV with any encoding")
        content = self.csv_source.read()
        if hasattr(self.csv_source, "seek"):
            self.csv_source.seek(0)
        if isinstance(content, str):
            return pd.read_csv(io.StringIO(content))
        last_error = None
        for enc in encodings:
            try:
                return pd.read_csv(io.StringIO(content.decode(enc)))
            except UnicodeDecodeError as e:
                last_error = e
        raise last_error or Exception("Failed to decode CSV with any encoding")

    def _validate_columns(self) -> List[str]:
        missing = set(self.REQUIRED_COLUMNS) - set(self.df.columns)
        if missing:
            return [f"Missing required columns: {', '.join(sorted(missing))}"]
        return []

    def _clean_data(self) -> pd.DataFrame:
        df = self.df.copy()
        for col in df.columns:
            if df[col].dtype == object:  # strip text columns (avoids select_dtypes deprecation)
                df[col] = df[col].astype(str).str.strip()

        if "Salary" in df.columns:
            df["Salary"] = (
                df["Salary"].astype(str).str.replace(",", "").str.replace("$", "").str.strip()
            )
            df["Salary"] = pd.to_numeric(df["Salary"], errors="coerce").fillna(0)
        else:
            df["Salary"] = 0

        df["Level"] = pd.to_numeric(df["Level"], errors="coerce").fillna(0).astype(int)

        for col, default in (
            ("Department", "Unknown"),
            ("Work Activities", ""),
            ("Job Description", ""),
        ):
            if col not in df.columns:
                df[col] = default
            else:
                df[col] = df[col].fillna(default)
        return df

    # ── ID keying (the breaking fix) ─────────────────────────────────────────
    def _row_key(self, row, idx: int) -> str:
        """Employee ID if present and non-blank, else a stable per-row surrogate key."""
        if "Employee ID" in row.index:
            raw = row["Employee ID"]
            if pd.notna(raw):
                val = str(raw).strip()
                if val and val.lower() != "nan":
                    return val
        return f"__row_{idx}"

    def _build_positions(self):
        """Build ID-keyed position dicts and the name→keys map; resolve manager keys."""
        rows = []
        name_to_keys: Dict[str, List[str]] = {}
        for idx, (_, row) in enumerate(self.df.iterrows()):
            name = str(row["Name"]).strip()
            if name in ("", "nan"):
                continue
            key = self._row_key(row, idx)
            rows.append((key, name, row))
            name_to_keys.setdefault(name, []).append(key)

        warnings: List[str] = []

        # Duplicate-name detection (collision warning; tree stays intact via ID keys).
        dups = {n: ks for n, ks in name_to_keys.items() if len(ks) > 1}
        for name, ks in sorted(dups.items()):
            warnings.append(
                f"Duplicate employee name detected (kept distinct by Employee ID): "
                f"'{name}' → {len(ks)} positions ({', '.join(ks)})"
            )

        positions: List[Dict] = []
        for key, name, row in rows:
            manager_key, mgr_warn = self._resolve_manager(key, name, row, name_to_keys, dups)
            if mgr_warn:
                warnings.append(mgr_warn)
            positions.append(
                {
                    "employee_key": key,
                    "display_name": name,
                    "job_title": _s(row.get("Job Title")),
                    "grade": _s(row.get("Grade")),
                    "department": _s(row.get("Department", "Unknown")) or "Unknown",
                    "level": int(row["Level"]) if pd.notna(row["Level"]) else 0,
                    "manager_key": manager_key,
                    "manager_name": _s(row.get("Line Manager")),
                    "salary": float(row["Salary"]) if pd.notna(row["Salary"]) else 0.0,
                    "work_activities": _s(row.get("Work Activities", "")),
                }
            )
        return positions, warnings

    def _resolve_manager(self, key, name, row, name_to_keys, dups):
        """Resolve the 'Line Manager' name to a manager employee_key (or None for a root)."""
        mgr_name = _s(row.get("Line Manager"))
        if mgr_name in TOP_SENTINELS:
            return None, None
        candidates = [k for k in name_to_keys.get(mgr_name, []) if k != key]
        if not candidates:
            return None, f"Manager not found for {key} ('{name}'): '{mgr_name}'"
        if len(candidates) > 1:
            return (
                candidates[0],
                f"Ambiguous manager name '{mgr_name}' for {key} — linked to first match "
                f"{candidates[0]}",
            )
        return candidates[0], None

    def _build_graph(self, positions: List[Dict]) -> nx.DiGraph:
        """Directed graph keyed by employee_key; edges manager_key -> report_key."""
        g = nx.DiGraph()
        for p in positions:
            g.add_node(p["employee_key"], **p)
        for p in positions:
            mk = p["manager_key"]
            if mk and mk in g.nodes:
                g.add_edge(mk, p["employee_key"])
        return g

    # ── structural checks & metadata (carried over, ID-keyed) ────────────────
    def _detect_issues(self) -> List[str]:
        errors: List[str] = []
        if not self.graph:
            return errors
        try:
            cycles = list(nx.simple_cycles(self.graph))
            if cycles:
                errors.append(
                    "Circular reporting detected: "
                    + "; ".join(" -> ".join(c) for c in cycles[:3])
                )
        except Exception:  # noqa: BLE001
            pass
        roots = [n for n in self.graph.nodes() if self.graph.in_degree(n) == 0]
        if len(roots) > 1:
            errors.append(f"Multiple root nodes found ({len(roots)}): {', '.join(roots[:5])}")
        return errors

    def _calculate_metadata(self, positions: List[Dict]) -> Dict:
        total = len(positions)
        if total == 0:
            return {
                "total_employees": 0,
                "manager_count": 0,
                "ic_count": 0,
                "unique_grades": [],
                "organizational_layers": 0,
                "total_salary_cost": 0.0,
            }
        managers = {n for n in self.graph.nodes() if self.graph.out_degree(n) > 0}
        unique_grades = sorted({p["grade"] for p in positions if p["grade"]})
        max_level = max((p["level"] for p in positions), default=0)
        total_salary = sum(p["salary"] for p in positions)
        return {
            "total_employees": total,
            "manager_count": len(managers),
            "ic_count": total - len(managers),
            "unique_grades": unique_grades,
            "organizational_layers": max_level,
            "total_salary_cost": round(total_salary, 2),
        }

    def _empty(self, *warnings: str) -> Dict[str, Any]:
        return {
            "positions": [],
            "graph": None,
            "validation_warnings": list(warnings),
            "metadata": {},
        }


def _s(value) -> str:
    """Stringify a cell to a stripped str, treating NaN/None/'nan' as empty."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text
