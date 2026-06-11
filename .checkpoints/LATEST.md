# LATEST CHECKPOINT
**Updated:** 2026-06-11T00:00:00 (Phase 0)
**Phase:** P0 — Protocol & scaffold
**Last completed micro-task:** P0 scaffold — backend + frontend skeletons run, `mock_claude`
fixture + gate script in place, all memory files created, architecture doc moved to `/docs` and
its three decisions recorded in `DECISIONS.md`.
**In-flight micro-task:** none — Phase 0 is **PARKED / held open** pending the missing `legacy/`
folder (see Open questions). Everything that does not depend on `legacy/` is done and committed.
**Next action (be exact):** WAIT for Eric to confirm and provide the `legacy/` folder (his v1
`claude-org-design-analyzer` app). When it arrives, complete the two remaining P0 ports:
  1. Extract the JSON parse/repair helpers from `legacy/.../work_activities_service.py` into
     `backend/app/services/_json_utils.py` (port, do not rewrite), and add a unit test for them.
  2. Copy the PAX CSV + expected-metrics fixture from `legacy/backend/tests/fixtures/` into
     `backend/tests/fixtures/` (this is baseline fixture #1 for the P1 PAX parity test).
Then re-run the gate, update BASELINE.md, commit, push, and only then is Phase 0 fully closed.
Do NOT start Phase 1 until Eric confirms Phase 0 looks good.
**Test status:** PASS — gate green (backend pytest + frontend `npm run build`). See PROGRESS.md
for the exact counts from this session.
**Recovery commands:** `bash scripts/gate.sh`  (equivalently: `cd backend && . .venv/bin/activate
&& pytest tests/ -v ; cd ../frontend && npm run build`)
**Open questions for Eric:**
  1. **BLOCKER — the `legacy/` folder is missing.** The Build Spec (B0) says you place a read-only
     copy of your v1 app (`claude-org-design-analyzer`) in a folder named `legacy/` at the repo
     root, and that I must PORT (not reinvent) these from it: the metrics engine, the ID-keyed CSV
     parser, the archetypes reference, the `work_activities_service.py` JSON helpers, and the **PAX
     test fixture (CSV + expected metrics)**. That folder is not in the repo. I have completed all
     of Phase 0 that does not depend on it and stopped exactly here per the spec's "do not reinvent"
     rule. **Please add the `legacy/` folder (drag your v1 app copy in, rename it `legacy`, commit
     & push), then tell me to resume.** Without it I cannot guarantee the P1 PAX parity numbers
     (64 employees, $5,770,000 cost, 6 layers) match your v1.
