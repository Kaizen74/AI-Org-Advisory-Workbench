# LATEST CHECKPOINT
**Updated:** 2026-06-11T00:30:00 (Phase 0 — COMPLETE)
**Phase:** P0 — Protocol & scaffold ✅ DONE
**Last completed micro-task:** P0.12 + P0.13 — ported the JSON parse/repair helpers from
`legacy/.../work_activities_service.py` into `backend/app/services/_json_utils.py` (with tests),
and placed baseline fixture #1 (`org_structure_PAX.csv` byte-identical copy + `expected_pax_metrics
.json`). Gate green at 13 tests.
**In-flight micro-task:** none. Phase 0 is fully closed and pushed. The `legacy/` folder blocker is
RESOLVED (Eric uploaded `legacy v1 app.zip` to `main`; extracted into `legacy/` on this branch).
**Next action (be exact):** WAIT for Eric to confirm Phase 0 looks good. On his go-ahead, START
**Phase 1 (P1 — Engagement core + diagnostics)**, first micro-task:
  1. Write the P1 micro-task checklist into `PROGRESS.md`.
  2. Create Alembic migration `001` for the engagement-core tables (clients, engagements, datasets,
     positions, metric_values) per Build Spec B1 — additive, reversible `downgrade()`.
  3. Port the CSV parser from `legacy/backend/app/parsers/csv_parser.py`, adapting to **Employee-ID
     keying with surrogate-key fallback + duplicate-name validation warning** (write the
     duplicate-name test FIRST, Part A Rule 6).
  4. Port the metrics engine from `legacy/.../metrics_service.py` to typed `metric_values`, then add
     the **PAX parity test** asserting 64 / 16 / 25.0 / 5,770,000 / 6 (baseline fixture #1).
Do NOT change any completed P0 file's behaviour without a DECISIONS.md entry (additive-only).
**Test status:** PASS — gate GREEN, 13 backend tests + clean frontend build
(`✅ GATE PASSED`). Recovery: `bash scripts/gate.sh`.
**Recovery commands:** `bash scripts/gate.sh`  (or: `cd backend && . .venv/bin/activate &&
PYTHONPATH=$PWD pytest tests/ -v ; cd ../frontend && npm run build`)
**Open questions for Eric:**
  1. (Resolved) The `legacy/` folder is now present (extracted from your `legacy v1 app.zip`).
  2. Minor housekeeping (no action needed now): your `legacy v1 app.zip` lives on the `main` branch;
     this `claude/compassionate-knuth-wx5bjq` branch carries the unpacked `legacy/` folder instead.
     When this branch merges to `main`, you may delete the zip from `main` to avoid duplication.
