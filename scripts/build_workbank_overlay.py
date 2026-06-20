#!/usr/bin/env python3
"""Build a curated WORKBank AI-potential overlay from the WORKBank dataset (D25/D26).

The conversion logic lives in `backend/app/services/workbank_ingest.py` (importable + unit-tested);
this is a thin CLI around it.

DATA SOURCE — WORKBank (Stanford SALT-NLP, arXiv:2506.06576). Per-task tables are on Hugging Face:
    https://huggingface.co/datasets/SALT-NLP/WORKBank
Three CSVs are used:
    task_data/task_statement_with_metadata.csv
    expert_ratings/expert_rated_technological_capability.csv
    worker_data/domain_worker_desires.csv

USAGE
    1. Ensure huggingface.co is reachable (allowlist it in your environment's network egress settings),
       then clone the dataset into a (git-ignored) ./workbank folder:
         git clone https://huggingface.co/datasets/SALT-NLP/WORKBank workbank
       (the three CSVs are found recursively, so the HF nested layout works as-is)
    2. python scripts/build_workbank_overlay.py [--src ./workbank] [--limit 300]
    3. Commit the curated subset it writes:
         backend/app/resources/taxonomies/workbank_overlay.curated.json
       The loader (taxonomy_loader.WORKBANK_OVERLAY_PATH) picks it up automatically and it becomes the
       authoritative overlay (source="WORKBank"). Keep the subset small (Build Spec A4 — ~200MB budget).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.workbank_ingest import build_overlay_from_dir  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "backend" / "app" / "resources" / "taxonomies" / "workbank_overlay.curated.json"


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a curated WORKBank overlay.")
    ap.add_argument("--src", type=Path, default=Path("./workbank"),
                    help="Folder holding the cloned/downloaded WORKBank dataset (CSVs found recursively, "
                         "so the HF repo's nested layout works as-is).")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output overlay JSON path.")
    ap.add_argument("--limit", type=int, default=None, help="Keep only the top-N occupations by capability.")
    args = ap.parse_args()

    overlay = build_overlay_from_dir(args.src, args.limit)
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
