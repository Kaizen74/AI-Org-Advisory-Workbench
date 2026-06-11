# PROGRESS — build journal (append-only)

One dated entry per session and per completed phase. Never rewrite history.

---

## Phase 0 — Protocol & scaffold

**Micro-task checklist (written before starting, per Part A):**
- [x] P0.1 — Copy Part A into root `CLAUDE.md` + current-state summary.
- [x] P0.2 — Create `.gitignore` (data-hygiene rules) BEFORE any commit.
- [x] P0.3 — Create `.checkpoints/{LATEST,BASELINE,DECISIONS}.md` and `PROGRESS.md`.
- [x] P0.4 — Create the README stub per spec B7 (non-technical owner).
- [x] P0.5 — Move `WORKFORCE_INTELLIGENCE_ARCHITECTURE.md` to `/docs`, read it, record the two
      carried-over decisions + one superseded decision in `DECISIONS.md`.
- [x] P0.6 — Verify companion files present (`taxonomy_seed.starter.json`, PRD, spec). **Verify
      `legacy/` present → MISSING (recorded as blocker).**
- [x] P0.7 — Scaffold backend (FastAPI) skeleton that runs.
- [x] P0.8 — Scaffold frontend (Vite + React + TS + Tailwind) skeleton that builds.
- [x] P0.9 — `mock_claude` pytest fixture in `backend/tests/conftest.py` + a fixtures JSON +
      smoke tests.
- [x] P0.10 — `scripts/gate.sh` + `Makefile` (`make gate`) — one-command regression gate.
- [x] P0.11 — First commit + push to GitHub.
- [ ] P0.12 — **BLOCKED on `legacy/`:** port `_json_utils.py` from `work_activities_service.py`.
- [ ] P0.13 — **BLOCKED on `legacy/`:** copy PAX CSV + expected-metrics fixture (baseline #1).

### Session 1 — 2026-06-11

- Read all four governing documents in full (Build Spec Part A first, then Part B; PRD; legacy
  architecture; taxonomy seed). Confirmed `python3 3.11`, `node v22`, `npm 10` available and that
  pip + npm have network access in this environment.
- Created the data-hygiene `.gitignore` **first**, before any commit, so no `*.db`, `.env`, client
  CSV, upload dir, or generated deliverable can ever reach GitHub.
- Wrote `CLAUDE.md` (full Part A + current-state summary), `PROGRESS.md`, and the three checkpoint
  files. Moved the WI architecture doc to `/docs`; recorded D1 (logical overlay join), D2 (three-
  layer separation) as carried over and D3 (single cross-boundary FK) as superseded — plus D4
  (dev branch) and D5 (legacy blocker) — in `DECISIONS.md`.
- Wrote the README stub for a non-technical owner per B7 (sections 1–8 stubbed; run/deploy detail
  filled out as phases ship).
- Scaffolded a runnable FastAPI backend (`/health`), the `claude_service` singleton, the
  `mock_claude` fixture (monkeypatches the Anthropic client to return canned JSON, zero network),
  and smoke tests. Scaffolded a Vite + React + TS + Tailwind frontend that builds with zero TS
  errors. Wired `scripts/gate.sh` and `make gate`.
- **BLOCKER discovered & recorded:** the `legacy/` folder is missing. Per spec B0 I did NOT
  reinvent the `_json_utils` port or the PAX fixture; Phase 0 is held open for them. Asked Eric to
  provide `legacy/`. See `.checkpoints/LATEST.md` → Open questions.
- Ran the regression gate: GREEN. Committed and pushed each step to
  `claude/compassionate-knuth-wx5bjq`.
