#!/usr/bin/env python3
"""Build a curated WORKBank AI-potential overlay from the WORKBank dataset (D25).

WHY
    The repo seed (`taxonomy_seed.starter.json`) ships only a tiny, ILLUSTRATIVE air-transport overlay.
    For robust, sector-agnostic AI benchmarking we want the REAL WORKBank values (worker desire +
    expert technological capability + Human Agency Scale) as the authoritative overlay, so the app
    relies on Claude HAS-rubric inference only as a last-resort fallback (see infer-potential).

DATA SOURCE
    WORKBank (Stanford SALT-NLP, "Future of Work with AI Agents", arXiv:2506.06576). The analysis
    *code* is on GitHub (SALT-NLP/workbank); the per-task tables are on Hugging Face:
        https://huggingface.co/datasets/SALT-NLP/WORKBank
    Three CSVs are used:
        task_data/task_statement_with_metadata.csv          (task -> O*NET-SOC occupation)
        expert_ratings/expert_rated_technological_capability.csv  (task -> capability, feasible HAS)
        worker_data/domain_worker_desires.csv               (task -> automation desire, desired HAS)

USAGE
    1. Download the three CSVs (huggingface.co must be reachable / allowlisted), e.g.:
         huggingface-cli download SALT-NLP/WORKBank --repo-type dataset --local-dir ./workbank_csv
       (or download them manually from the HF "Files" tab into one directory).
    2. python scripts/build_workbank_overlay.py --src ./workbank_csv
    3. Commit the resulting curated subset:
         backend/app/resources/taxonomies/workbank_overlay.curated.json
       The loader (taxonomy_loader.WORKBANK_OVERLAY_PATH) picks it up automatically and it becomes the
       authoritative overlay (source="WORKBank"), keyed by O*NET-SOC code.

NOTES
    * Column names are matched FUZZILY (by keyword) so minor schema changes don't break the build —
      the actual columns are documented in the WORKBank codebook.pdf; verify the mapping it prints.
    * Per the deployment budget (Build Spec A4) commit a CURATED SUBSET, not the full dataset; use
      --limit / --functions to keep it small and relevant to your clients.
    * WORKBank values are aggregated to the O*NET-SOC occupation level (mean capability/desire, modal
      Human Agency level), matching how the benchmark step keys overlays (onet_task_code).
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "backend" / "app" / "resources" / "taxonomies" / "workbank_overlay.curated.json"


def _find_col(fieldnames: List[str], *keywords: str) -> Optional[str]:
    """Return the first column whose lowercased name contains ALL keywords (fuzzy, schema-tolerant)."""
    for name in fieldnames:
        low = name.lower()
        if all(k in low for k in keywords):
            return name
    return None


def _read(path: Path) -> List[dict]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _num(val: str) -> Optional[float]:
    try:
        return float(str(val).strip())
    except (TypeError, ValueError):
        return None


def _norm_0_1(values: List[float]) -> List[float]:
    """Normalise to 0..1. If the values look like a 1..5 (or 0..5) Likert scale, rescale by max."""
    if not values:
        return values
    hi = max(values)
    if hi > 1.0:
        return [v / hi for v in values]
    return values


def _zone(capability: Optional[float], has_level: Optional[int]) -> str:
    """GREEN_LIGHT = strong agentic fit (high capability, low required human agency); else RED_LIGHT."""
    if capability is not None and capability >= 0.60 and (has_level or 5) <= 2:
        return "GREEN_LIGHT"
    return "RED_LIGHT"


def build(src: Path, limit: Optional[int]) -> List[dict]:
    meta = _read(src / "task_statement_with_metadata.csv")
    cap = _read(src / "expert_rated_technological_capability.csv")
    des = _read(src / "domain_worker_desires.csv")

    # ── locate columns fuzzily ──
    m_task = _find_col(list(meta[0]), "task", "id") or _find_col(list(meta[0]), "task")
    m_soc = _find_col(list(meta[0]), "onet") or _find_col(list(meta[0]), "soc") or _find_col(list(meta[0]), "occupation", "code")
    m_occ = _find_col(list(meta[0]), "occupation", "title") or _find_col(list(meta[0]), "occupation")
    m_text = _find_col(list(meta[0]), "task", "statement") or _find_col(list(meta[0]), "statement")
    c_task = _find_col(list(cap[0]), "task", "id") or _find_col(list(cap[0]), "task")
    c_cap = _find_col(list(cap[0]), "capability") or _find_col(list(cap[0]), "tech")
    c_has = _find_col(list(cap[0]), "agency") or _find_col(list(cap[0]), "has")
    d_task = _find_col(list(des[0]), "task", "id") or _find_col(list(des[0]), "task")
    d_des = _find_col(list(des[0]), "desire") or _find_col(list(des[0]), "automat")

    print("Detected columns:")
    print(f"  meta: task={m_task} soc={m_soc} occupation={m_occ} text={m_text}")
    print(f"  capability: task={c_task} capability={c_cap} has={c_has}")
    print(f"  desire: task={d_task} desire={d_des}")
    if not (m_task and m_soc and c_task and c_cap):
        raise SystemExit("Could not detect required columns — inspect the CSV headers / codebook.pdf.")

    cap_by_task = {r[c_task]: r for r in cap}
    des_by_task = {r[d_task]: r for r in des} if d_task else {}

    # normalise capability / desire across the corpus
    cap_vals = _norm_0_1([v for v in (_num(r.get(c_cap)) for r in cap) if v is not None])
    cap_norm = {r[c_task]: cv for r, cv in zip(cap, cap_vals)} if cap_vals else {}

    by_soc: Dict[str, dict] = defaultdict(lambda: {"cap": [], "has": [], "des": [], "occ": None, "text": None})
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
        if c_has and tid in cap_by_task:
            h = _num(cap_by_task[tid].get(c_has))
            if h is not None:
                agg["has"].append(h)
        if d_des and tid in des_by_task:
            dv = _num(des_by_task[tid].get(d_des))
            if dv is not None:
                agg["des"].append(dv)

    des_all = [v for a in by_soc.values() for v in a["des"]]
    des_hi = max(des_all) if des_all else 1.0

    overlay: List[dict] = []
    for soc, a in sorted(by_soc.items()):
        capability = round(statistics.fmean(a["cap"]), 3) if a["cap"] else None
        has_level = int(round(statistics.fmean(a["has"]))) if a["has"] else None
        if has_level is not None:
            has_level = max(1, min(5, has_level))
        desire = round(statistics.fmean(a["des"]) / des_hi, 3) if a["des"] and des_hi else None
        overlay.append({
            "onet_task_code": soc,
            "occupation": a["occ"],
            "onet_task_text": a["text"],
            "has_level": has_level,
            "capability_score": capability,
            "desire_score_us": desire,  # US worker preference (WORKBank) — never local
            "zone": _zone(capability, has_level),
            "source": "WORKBank",
        })
    overlay.sort(key=lambda o: (o["capability_score"] or 0), reverse=True)
    if limit:
        overlay = overlay[:limit]
    return overlay


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a curated WORKBank overlay (D25).")
    ap.add_argument("--src", type=Path, default=Path("./workbank_csv"),
                    help="Directory holding the three WORKBank CSVs downloaded from Hugging Face.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output overlay JSON path.")
    ap.add_argument("--limit", type=int, default=None, help="Keep only the top-N occupations by capability.")
    args = ap.parse_args()

    overlay = build(args.src, args.limit)
    payload = {
        "_meta": {
            "source": "WORKBank (Stanford SALT-NLP, arXiv:2506.06576)",
            "url": "https://huggingface.co/datasets/SALT-NLP/WORKBank",
            "note": "Aggregated to O*NET-SOC occupation level. desire_score_us is US worker preference. "
                    "Verify/refine before client use.",
            "rows": len(overlay),
        },
        "task_ai_overlay": overlay,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(overlay)} WORKBank overlay rows -> {args.out}")


if __name__ == "__main__":
    main()
