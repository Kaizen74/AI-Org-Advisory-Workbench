"""Convert the WORKBank dataset (Stanford SALT-NLP, arXiv:2506.06576) into our AI-overlay schema.

The WORKBank per-task tables (Human Agency Scale, expert technological capability, worker desire) are
hosted on Hugging Face (https://huggingface.co/datasets/SALT-NLP/WORKBank). Download the three CSVs into
one directory, then this module aggregates them to the O*NET-SOC occupation level (matching how the
benchmark step keys overlays via `onet_task_code`) and emits rows for `taxonomy_loader._upsert_overlay`.

This is the AUTHORITATIVE AI-potential layer: once a curated WORKBank overlay is present, the benchmark
relies on Claude HAS-rubric inference only as a last resort. Values are aggregated/illustrative until
verified — keep `review_state` gating in place.

Pure/​deterministic so it is unit-testable offline (no network).
"""
from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional


def find_col(fieldnames: List[str], *keywords: str) -> Optional[str]:
    """First column whose lowercased name contains ALL keywords (fuzzy → schema-tolerant)."""
    for name in fieldnames:
        low = name.lower()
        if all(k in low for k in keywords):
            return name
    return None


def _read(path: Path) -> List[dict]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _locate(src: Path, filename: str) -> Optional[Path]:
    """Find a WORKBank CSV under `src`, whether flat or in the HF repo's nested layout
    (task_data/, expert_ratings/, worker_data/). Returns None if not found."""
    direct = src / filename
    if direct.exists():
        return direct
    matches = sorted(src.rglob(filename))
    return matches[0] if matches else None


def _num(val) -> Optional[float]:
    try:
        return float(str(val).strip())
    except (TypeError, ValueError):
        return None


def derive_zone(capability: Optional[float], has_level: Optional[int]) -> str:
    """GREEN_LIGHT = strong agentic fit (high capability + low required human agency); else RED_LIGHT."""
    if capability is not None and capability >= 0.60 and (has_level or 5) <= 2:
        return "GREEN_LIGHT"
    return "RED_LIGHT"


def build_overlay_from_dir(src: Path, limit: Optional[int] = None) -> List[Dict]:
    """Read the three WORKBank CSVs from `src` and return overlay rows aggregated per O*NET-SOC code.

    Capability and desire are normalised to 0..1 (rescaled by max if they look like Likert scales);
    has_level is the modal/mean Human Agency level clamped to 1..5; zone is derived.
    """
    src = Path(src)
    meta_path = _locate(src, "task_statement_with_metadata.csv")
    cap_path = _locate(src, "expert_rated_technological_capability.csv")
    des_path = _locate(src, "domain_worker_desires.csv")
    if meta_path is None or cap_path is None:
        raise FileNotFoundError(
            f"WORKBank CSVs not found under {src}. Clone the dataset there, e.g. "
            "`git clone https://huggingface.co/datasets/SALT-NLP/WORKBank workbank` "
            "(requires huggingface.co in your network allowlist)."
        )
    meta = _read(meta_path)
    cap = _read(cap_path)
    des = _read(des_path) if des_path else []
    if not meta or not cap:
        raise ValueError("WORKBank CSVs missing or empty (task metadata + expert capability required).")

    m_task = find_col(list(meta[0]), "task", "id") or find_col(list(meta[0]), "task")
    m_soc = (find_col(list(meta[0]), "onet", "code") or find_col(list(meta[0]), "soc")
             or find_col(list(meta[0]), "occupation", "code"))
    m_occ = find_col(list(meta[0]), "occupation", "title") or find_col(list(meta[0]), "occupation")
    # task statement column: prefer an exact "task" header that is NOT the id column
    m_text = (find_col(list(meta[0]), "task", "statement") or find_col(list(meta[0]), "statement")
              or next((c for c in meta[0] if c.strip().lower() == "task"), None))
    c_task = find_col(list(cap[0]), "task", "id") or find_col(list(cap[0]), "task")
    # WORKBank's expert capability column is "Automation Capacity Rating".
    c_cap = (find_col(list(cap[0]), "capability") or find_col(list(cap[0]), "capacity")
             or find_col(list(cap[0]), "automation", "rating") or find_col(list(cap[0]), "tech"))
    c_has = find_col(list(cap[0]), "agency") or find_col(list(cap[0]), "has")  # expert (feasible) HAS
    d_task = (find_col(list(des[0]), "task", "id") or find_col(list(des[0]), "task")) if des else None
    d_des = (find_col(list(des[0]), "desire", "rating") or find_col(list(des[0]), "desire")) if des else None

    if not (m_task and m_soc and c_task and c_cap):
        raise ValueError(
            f"Could not detect required columns (task={m_task} soc={m_soc} "
            f"cap_task={c_task} capability={c_cap}). Check headers vs the WORKBank codebook."
        )

    def _mean_by_task(rows: List[dict], task_col: str, val_col: Optional[str]) -> Dict[str, float]:
        """Average a rating across all raters of the same task (multi-rater files)."""
        acc: Dict[str, List[float]] = defaultdict(list)
        if not val_col:
            return {}
        for r in rows:
            v = _num(r.get(val_col))
            if v is not None and r.get(task_col) is not None:
                acc[r[task_col]].append(v)
        return {tid: statistics.fmean(vs) for tid, vs in acc.items() if vs}

    cap_raw = _mean_by_task(cap, c_task, c_cap)            # expert automation-capacity, per task
    has_raw = _mean_by_task(cap, c_task, c_has)            # expert feasible HAS, per task
    des_raw = _mean_by_task(des, d_task, d_des) if d_task else {}  # worker automation desire, per task

    # normalise capability / desire to 0..1 (rescale by observed max if it looks like a Likert scale)
    cap_hi = max(cap_raw.values(), default=1.0) or 1.0
    des_hi = max(des_raw.values(), default=1.0) or 1.0
    cap_norm = {t: (v / cap_hi if cap_hi > 1.0 else v) for t, v in cap_raw.items()}
    des_norm = {t: (v / des_hi if des_hi > 1.0 else v) for t, v in des_raw.items()}

    by_soc: Dict[str, dict] = defaultdict(
        lambda: {"cap": [], "has": [], "des": [], "occ": None, "text": None}
    )
    for r in meta:
        soc = (r.get(m_soc) or "").strip()
        tid = r.get(m_task)
        if not soc or tid is None:
            continue
        agg = by_soc[soc]
        agg["occ"] = agg["occ"] or (r.get(m_occ) if m_occ else None)
        agg["text"] = agg["text"] or (r.get(m_text) if m_text else None)
        if tid in cap_norm:
            agg["cap"].append(cap_norm[tid])
        if tid in has_raw:
            agg["has"].append(has_raw[tid])
        if tid in des_norm:
            agg["des"].append(des_norm[tid])

    overlay: List[Dict] = []
    for soc, a in sorted(by_soc.items()):
        capability = round(statistics.fmean(a["cap"]), 3) if a["cap"] else None
        has_level = int(round(statistics.fmean(a["has"]))) if a["has"] else None
        if has_level is not None:
            has_level = max(1, min(5, has_level))
        desire = round(statistics.fmean(a["des"]), 3) if a["des"] else None
        # Only emit occupations WORKBank actually rated — a no-signal row would otherwise shadow the
        # Claude inference fallback (the SOC would "match" an overlay carrying no AI-potential data).
        if capability is None and has_level is None:
            continue
        overlay.append({
            "onet_task_code": soc,
            "occupation": a["occ"],
            "onet_task_text": a["text"],
            "has_level": has_level,
            "capability_score": capability,
            "desire_score_us": desire,  # US worker preference (WORKBank) — never local (A4)
            "zone": derive_zone(capability, has_level),
            "source": "WORKBank",
        })
    overlay.sort(key=lambda o: (o["capability_score"] or 0), reverse=True)
    return overlay[:limit] if limit else overlay
