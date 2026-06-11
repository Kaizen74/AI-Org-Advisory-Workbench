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
- [x] P0.12 — Ported `_json_utils.py` from `work_activities_service.py` (+ 7 tests).
- [x] P0.13 — Placed PAX CSV (byte-identical) + `expected_pax_metrics.json` (baseline #1) (+ 2 tests).

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

### Session 2 — 2026-06-11 (Phase 0 closed)

- Eric resolved the blocker by uploading `legacy v1 app.zip` to the `main` branch. Fetched it,
  extracted the blob, and unpacked the v1 app into a `legacy/` folder on this branch (81 archive
  entries → 61 tracked files; scanned clean — no `*.db`, `.env`, or `node_modules`).
- **P0.12** — Ported the JSON parse/repair helpers (`_parse_response`, `_repair_truncated_json`,
  `_extract_partial_data`) out of `legacy/.../work_activities_service.py` into
  `backend/app/services/_json_utils.py` as shared module functions (behaviour preserved). Added
  `test_json_utils.py` (7 tests) locking the legacy contract — including the subtle rule that the
  raw-JSON path needs a closing `}` before repair is attempted.
- **P0.13** — Copied `org_structure_PAX.csv` byte-identically (md5 verified) into
  `backend/tests/fixtures/` and recorded `expected_pax_metrics.json` (64 / 16 / 25.0 / 5,770,000 /
  6) as baseline fixture #1. Added `test_pax_fixture.py` (2 tests). Full PAX parity test deferred to
  P1 with the metrics-engine port (per B4).
- One self-inflicted red during the session: my first `test_parse_repairs_truncated_and_flags_it`
  asserted the wrong legacy behaviour; corrected the **test** (the ported code was faithful) into
  two precise tests. Gate then GREEN at **13 tests** + clean frontend build.
- Committed and pushed. **Phase 0 is complete.** Awaiting Eric's go-ahead for Phase 1.

---

## Phase 1 — Engagement core + diagnostics

**Micro-task checklist (written before starting, per Part A; each ends with a commit + LATEST update):**
- [x] P1.1 — Backend DB foundation (async engine, Base, get_session; pandas/networkx/greenlet;
      Alembic scaffolding).
- [x] P1.2 — Engagement-core models + cascade-purge test.
- [x] P1.3 — Alembic migration 001 (additive, reversible) + round-trip test.
- [x] P1.4 — CSV parser port with Employee-ID keying + surrogate fallback + duplicate-name warning
      (test-first). Faithful to v1.
- [x] P1.5 — Metrics engine port (ID-keyed) + PAX parity + byte-stable snapshot. Baseline LOCKED at
      the provided CSV's actual values per D9 (64 / 34 / 53.1 / 6,620,000 / 6).
- [x] P1.6 — Diagnostics service: typed `metric_values` flattening + async compute/persist.
- [x] P1.7 — `engagement_service` + `/api/v1/engagements` (CRUD, CSV upload, purge).
- [x] P1.8 — `diagnostics_service` + `/api/v1/diagnostics` (compute/summary/archetypes/activator).
- [x] P1.9 — Archetype reference ported byte-identical + `GET /archetypes`.
- [x] P1.10 — Five-Activator leading-indicator pre-screen + `GET /activator-screen`.
- [x] P1.11 — Frontend Engagements + Diagnostics pages + typed API client.
- [x] P1.12 — Phase close: gate green, BASELINE locked, checkpoints + README updated, pushed.

### Session 3 — 2026-06-11 (Phase 1 start)

- Eric approved Phase 0 ("Proceed"). Read the legacy CSV parser, metrics engine, models, DB layer,
  and CSV-parser tests to plan a faithful port. Confirmed the legacy graph is **name-keyed** — P1's
  mandated breaking fix is to re-key on Employee ID (PRD M1). Wrote the P1 micro-task checklist
  above and began executing it micro-task by micro-task.
- Built the DB foundation, engagement-core models (+ cascade purge), Alembic migration 001
  (additive + reversible round-trip test).
- **Data conflict found & escalated (D8→D9):** the provided `org_structure_PAX.csv` yields
  64 / 34 / 53.1% / $6,620,000 / 6 — the faithful port reproduces the legacy v1 code's output on it
  exactly — but the spec's parity target was 64 / 16 / 25.0 / $5,770,000 / 6. Since total_cost is a
  raw salary sum, the zip's CSV is a different file than the spec was written against. Eric chose
  "use the provided CSV as truth"; reset and LOCKED the parity baseline to the actual values.
- Ported the CSV parser (ID-keyed + dup-name warning) and metrics engine; added the PAX parity +
  byte-stable snapshot. Built the diagnostics service (typed `metric_values`), the engagement +
  diagnostics routers, ported the 7-archetype reference, and added the Five-Activator pre-screen.
  Built the frontend Engagements + Diagnostics pages with a typed API client.
- Verified a **live** uvicorn run end-to-end (migration → create client/engagement → upload PAX →
  compute → 64 / 34 / $6.62M / 6). Gate GREEN: **33 backend tests + clean frontend build**.
  **Phase 1 complete.** Awaiting Eric's go-ahead for Phase 2.
