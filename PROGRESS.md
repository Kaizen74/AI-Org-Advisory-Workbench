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

---

## Phase 2 — Task Intelligence

**Micro-task checklist (written before starting, per Part A; each ends with a commit + LATEST update):**
- [x] P2.1 — Reference-layer + task models (8) + model smoke test.
- [x] P2.2 — Migration 002 (additive, reversible) + round-trip test.
- [x] P2.3 — Seed moved into resources; idempotent loader (dual-desire mapping; 0.40 → unreviewed);
      4 loader tests.
- [x] P2.4 — Batched extraction + deterministic merge; 500-position synthetic fixture (3 tests).
- [x] P2.5 — Benchmark step (status + provenance + confidence routing).
- [x] P2.6 — AI-opportunity (logical O*NET overlay join; robotics lever; L0–L3) + provenance test.
- [x] P2.7 — Rollups (department/layer/overall) + `GET /quick` (no key).
- [x] P2.8 — `/api/v1/task-intel` router + guards (400 no key, 404 no dataset); 3 integration tests.
- [x] P2.9 — Frontend Task Intelligence page (pipeline runner, L0–L3 + HAS charts, caveats).
- [x] P2.10 — Phase close: gate green (49 tests), BASELINE + checkpoints + README updated, pushed.

### Session 4 — 2026-06-11 (Phase 2 start)

- Eric approved Phase 1 ("Proceed"). Wrote the P2 checklist and began executing micro-task by
  micro-task. Binding constraints kept front-of-mind: WORKBank guardrails (A4), the
  logical-overlay-join (D1), and confidence<0.70 → unreviewed (the seed's 0.40 crosswalk row).
- Built the reference + task schema (migration 002, additive/reversible), the idempotent seed
  loader (dual-desire mapping; 0.40 crosswalk → unreviewed), and the full mocked-AI pipeline:
  batched extraction (500-position synthetic fixture proving batching + deterministic merge),
  benchmarking (provenance + confidence routing), and AI-opportunity via the logical O*NET overlay
  join (physical tasks → model-inferred robotics levers; deterministic L0–L3). Added rollups and the
  `/api/v1/task-intel` router with guards (400 no key, 404 no dataset; `/quick` key-free). Built the
  frontend Task Intelligence page. Provenance-presence asserted on every AI row (A4).
- Gate GREEN: **49 backend tests + clean frontend build**. **Phase 2 complete.** Awaiting Eric's
  go-ahead for Phase 3 (Validation queue + local desire).

---

## Phase 3 — Validation queue + local desire

**Micro-task checklist (written before starting, per Part A; each ends with a commit + LATEST update):**
- [x] P3.1 — `validation_service.get_queue` (benchmarks + ai_scores + crosswalks; confidence
      filter); queue catches the seed's 0.40 crosswalk.
- [x] P3.2 — `review_items` (bulk approve/edit/reject) + CURATED_BY_CONSULTANT crosswalk learning
      (idempotent); `get_stats`.
- [x] P3.3 — `client_ready` filter + test that unreviewed model-inferred is excluded (A4/M6).
- [x] P3.4 — `/api/v1/validation` router (queue/review/stats) + integration tests.
- [x] P3.5 — Desire pulse: xlsx instrument export + CSV/xlsx import → `desire_score_local` recompute
      (US score untouched); openpyxl dep.
- [x] P3.6 — Frontend ValidationQueue page (confidence filter, bulk approve/reject, source badges) +
      pulse download/import.
- [x] P3.7 — Phase close: gate green (54 tests), BASELINE + checkpoints + README, pushed.

### Session 5 — 2026-06-11 (Phase 3 start)

- Eric approved Phase 2 ("Proceed"). Wrote the P3 checklist and began executing. Binding rules:
  review is triggered by confidence (<0.70 → unreviewed), `desire_score_us` is never overwritten by
  local desire, approvals feed back as CURATED_BY_CONSULTANT, and unreviewed model-inferred content
  must be excluded from client-ready payloads (A4/M6).
- Built the validation service (unified queue across benchmarks/ai_scores/crosswalks; the seed's
  0.40 crosswalk surfaces), bulk review with CURATED_BY_CONSULTANT crosswalk learning, the
  client-ready filter, and the `/api/v1/validation` router. Built the desire-pulse service (xlsx
  instrument export + CSV/xlsx response import → `desire_score_local` recompute, US score untouched)
  with `/pulse` endpoints. Built the frontend Validation Queue page (confidence filter, bulk
  approve/reject, source badges) + pulse download/import.
- Gate GREEN: **54 backend tests + clean frontend build**. **Phase 3 complete.** Awaiting Eric's
  go-ahead for Phase 4 (Scenario Studio).

---

## Phase 4 — Scenario Studio

**Micro-task checklist (written before starting, per Part A; each ends with a commit + LATEST update):**
- [x] P4.1 — Models + migration 003 (additive, reversible) + round-trip test.
- [x] P4.2 — Pure move engine + apply/undo byte-parity property tests (test-first); 6 tests.
- [x] P4.3 — `scenario_service`: CRUD, moves, delta vs `metric_values`, compare, present/lock/fork.
- [x] P4.4 — `/api/v1/scenarios` router + 4 integration tests (present locks → 409; fork edits).
- [x] P4.5 — Baseline scenario-delta snapshot (fixed PAX sequence) + byte-parity test.
- [x] P4.6 — Frontend ScenarioStudio page (move builder + live delta + 3-way comparison).
- [x] P4.7 — Phase close: gate green (66 tests), BASELINE + checkpoints + README, pushed.

### Session 6 close — 2026-06-11

- Built scenario models + migration 003, the **pure move engine** (apply/undo byte-parity proven
  test-first), the scenario service (delta vs persisted `metric_values`, 3-way compare,
  present/lock/fork), the `/api/v1/scenarios` router, the scenario-delta baseline snapshot, and the
  frontend Scenario Studio page (move builder, live delta panel, comparison table).
- Gate GREEN: **66 backend tests + clean frontend build**. **Phase 4 complete.** Awaiting Eric's
  go-ahead for Phase 5 (Workflow Mapper + Transition Planner).

---

## Phase 5 — Workflow Mapper + Transition Planner

**Micro-task checklist (written before starting, per Part A; each ends with a commit + LATEST update):**
- [x] P5.1 — Models + migration 004 (additive, reversible) + round-trip test.
- [x] P5.2 — `workflow_service`: process/step CRUD, `map_tasks`, `opportunity_matrix` (L0–L3 counts
      + mocked-AI priority narrative).
- [x] P5.3 — `/api/v1/workflows` router + mocked-AI integration test.
- [x] P5.4 — `transition_service`: deterministic impact classes + mocked-AI SFw pathway suggestions.
- [x] P5.5 — `/api/v1/transition` router + register xlsx export + tests.
- [x] P5.6 — Frontend WorkflowMapper + TransitionPlanner pages + `GET /task-intel/tasks`.
- [x] P5.7 — Phase close: gate green (70 tests), BASELINE + checkpoints + README, pushed.

### Session 7 close — 2026-06-11

- Built process/step/task_link models + migration 004, the `workflow_service` (process CRUD,
  task→step mapping, deterministic L0–L3 opportunity matrix + mocked-AI priority), the
  `transition_service` (deterministic impact classes from scenario moves + mocked-AI SFw pathway
  suggestions, register xlsx export), both routers, and the frontend Workflow Mapper + Transition
  Planner pages. Added `GET /task-intel/tasks` for mapping.
- Gate GREEN: **70 backend tests + clean frontend build**. **Phase 5 complete.** Awaiting Eric's
  go-ahead for Phase 6 (Deliverable Factory).

---

## Phase 6 — Deliverable Factory

**Micro-task checklist (written before starting, per Part A; each ends with a commit + LATEST update):**
- [x] P6.1 — Deliverable model + migration 005 (additive, reversible) + round-trip test; pptx/docx
      deps; `backend/output/` gitignored.
- [x] P6.2 — `deliverable_theme` (minimal, D10) + pptx/docx builders; `provenance_summary` +
      export-block helper.
- [x] P6.3 — 6 generators (PPTX diagnostic/scenarios/roadmap, DOCX TOM, XLSX metrics/transition)
      with auto provenance disclosure.
- [x] P6.4 — Export-block test (unreviewed model-inferred excluded) + provenance presence.
- [x] P6.5 — `/api/v1/deliverables` router (generate/list/types/download) + tests.
- [x] P6.6 — Frontend Deliverables page.
- [x] P6.7 — Phase close: gate green (74 tests), BASELINE + checkpoints + README, pushed.

### Session 8 close — 2026-06-14

- Built the deliverable model + migration 005, the modern-minimalist theme + pptx/docx builders, the
  6 generators (each with an auto-generated provenance disclosure), the export-block (AI roadmap uses
  client-ready scores only; excluded count disclosed), the `/api/v1/deliverables` router, and the
  frontend Deliverables page. Files write to gitignored `backend/output/`.
- Gate GREEN: **74 backend tests + clean frontend build**. **Phase 6 complete.** Awaiting Eric's
  go-ahead for Phase 7 (Security & deploy).

---

## Pre-P7 feature block — Settings (branding, UI-managed API key, local-LLM fallback)

**Requested by Eric (2026-06-14) before P7.** Micro-task checklist:
- [x] FA.1 — `AppSetting` model + migration 006 + `settings_service` (DB + in-memory cache) + tests.
- [x] FA.2 — Routed `claude_service.complete` by provider (anthropic | local via httpx); public
      signatures preserved; regression + provider tests. (D11)
- [x] FA.3 — `/api/v1/settings` router (get/update masked, brand-logo upload/get, test-llm) + tests.
- [x] FA.4 — Brand deck: `theme_from_settings` + logo on title slide; `template="brand"` + tests. (D12)
- [x] FA.5 — Frontend Settings page + Deliverables template selector + Settings tab.
- [x] FA.6 — Startup cache hydration; comprehensive gate (90 tests, no regression); checkpoints; push.

**Session 9 outcome:** all three capabilities delivered + verified live (key set via UI persists;
provider switch to local routes to an OpenAI-compatible endpoint; brand logo/palette drive the deck).
Gate GREEN: **90 backend tests + clean frontend build**, zero regressions. Ready for P7 on Eric's go.

- **SATS brand preconfigured (2026-06-14):** extracted palette (red EE2536, grey D5D7D7, Arial) +
  logo from Eric's SATS Corporate Presentation Template; committed the logo as a resource; set SATS
  as the default brand (overridable in UI). `template="brand"` renders SATS out of the box. 91 tests.

---

## Phase 7 — Security & deploy

**Micro-task checklist (written before starting, per Part A):**
- [x] P7.1 — Anonymization end-to-end: salted pseudonym at ingest; exports use pseudonyms;
      **test: no real name in any export** (transition JSON + xlsx).
- [x] P7.2 — `audit_events` (migration 007) + `audit_service`; record uploads/AI/validation/
      deliverables/purge; `GET /api/v1/audit`.
- [x] P7.3 — Real-name purge (PDPA) endpoint (nulls `display_name`, keeps pseudonyms) + test.
- [x] P7.4 — Postgres compatibility + env hardening (ANON_SALT, asyncpg/psycopg2, `db_url.to_sync_url`).
- [x] P7.5 — Finalized README per B7 (Vercel+Railway deploy guide, troubleshooting table, data/
      privacy); deploy enablement (configurable API base, Procfile).
- [x] P7.6 — Phase close: gate green (100 tests), checkpoints, push. **Live deploy + verbatim README
      verification handed to Eric (needs his Vercel/Railway accounts + a browser).**

### Session 10 — 2026-06-14 (Phase 7)

- Eric supplied the SATS template (preconfigured) and approved P7. Built the full security layer:
  anonymization end-to-end (pseudonyms at ingest; transition register JSON + xlsx carry no real
  names — test-enforced), the audit trail (`audit_events` + `audit_service` wired into uploads/AI/
  validation/deliverables/purge), and the PDPA real-name purge. Hardened for Postgres (asyncpg/
  psycopg2 drivers, `db_url.to_sync_url`, dialect-compile test) and env (`ANON_SALT`, `CORS_ORIGINS`).
  Made the frontend API base configurable (`VITE_API_BASE_URL`) + added a Railway `Procfile`, and
  finalized the B7 README (click-by-click Vercel+Railway deploy, troubleshooting table, privacy).
  Replaced the deprecated `on_event` with a lifespan handler.
- Gate GREEN: **100 backend tests + clean frontend build**, zero regressions. **P7 code complete.**
  Remaining: the live cloud deploy + following the README verbatim — needs Eric's accounts/browser.
  **All seven phases (P0–P7) are now built.**

### Session 11 — 2026-06-14 (Private access control, D13)

- Eric required the app to be **private** (not public): selected people sign in with email + passcode
  so the SATS look-and-feel is never shown publicly. Built `access_users` (migration 008),
  `access_service` (PBKDF2 hashing, bootstrap from `ACCESS_USERS`), `token_service` (HMAC-signed
  tokens, stdlib — no JWT dep), an auth dependency gating **every `/api/v1/*` route except `auth`**
  (`/health` stays open), `/auth/login|me`, and owner-only `/api/v1/access` allowlist management.
  Frontend: a neutral login screen, token storage + `Authorization` header + 401→sign-out, and an
  owner-only Access-control panel in Settings. Added `python-dotenv` so local `.env` is read.
  Updated the README deploy guide for private hosting (`AUTH_SECRET`, `ACCESS_USERS`).
- Tests: `api_client` overrides the auth dep (existing suites unaffected); `anon_client` exercises
  the real gate. **108 backend tests + clean frontend build; zero regressions.** Live-verified:
  unauthenticated 401 → login token → authenticated 200. Decision D13 recorded.

### Session 9 — 2026-06-14 (pre-P7 Settings block)

- Eric requested three additive capabilities before P7: swappable brand logo/palette driving the deck
  template; the Anthropic API key captured/stored via the UI; and a local-LLM fallback for frontier-
  model outages. Recorded D11 (UI key + local provider, supersedes A4 "Claude only") and D12 (brand
  theme). Building with full mock tests + a regression-safe gate.

### Session 8 — 2026-06-14 (Phase 6 start)

- Eric approved Phase 5 ("Proceed to Phase 6") and asked for a modern-minimalist deck template
  (referencing his 'business ideas' project — not accessible from this repo-scoped session, so a
  neutral minimalist palette is used for now; recorded as D10). Wrote the P6 checklist and began.

### Session 7 — 2026-06-11 (Phase 5 start)

- Eric approved Phase 4 ("Proceed"). Wrote the P5 checklist and began executing. Impact classes are
  derived deterministically from a scenario's moves; skill-gap pathway suggestions are model-inferred
  + unreviewed (carry provenance, excluded from client-ready exports per A4/M6).

### Session 6 — 2026-06-11 (Phase 4 start)

- Eric approved Phase 3 ("Proceed"). Wrote the P4 checklist and began executing. Critical guarantee:
  `apply_moves` is a PURE function (deep-copies baseline, never mutates) so undo = recompute from
  baseline + remaining moves reproduces baseline metrics byte-identically. Deltas computed vs
  persisted `metric_values`, not re-parsed CSV.

---

## 2026-06-15 — Bugfix session (D14): cost metrics ignored salaries from real uploads

**Reported:** Eric's "Global Mkrting Co" upload showed **TOTAL COST $0** though the CSV had a
populated salary column.
**Diagnosis:** `OrgCSVParser._clean_data` matched the salary column by the exact header `"Salary"`;
the real export's header is `"Salary ($)"`, so no column matched → every `salary` = 0 →
`cost_analysis.total_cost = 0`. PAX fixture uses exact `"Salary"`, so the LOCKED baseline never
exposed it.
**Fix (Rule 4, test-first):**
1. Added failing tests `test_csv_parser.py::test_salary_column_header_variants_are_recognized` and
   `::test_currency_formatted_salary_values_are_parsed`.
2. Added `OrgCSVParser._find_salary_column`: exact `"Salary"` wins, else first header containing
   "salary" (covers `Salary ($)`, `Salary (USD)`, `Annual Salary`, `Base Salary`, `SALARY`).
   Existing `$`/`,` stripping and `NA→0` coercion unchanged.
3. Full gate green.
**Verification:** end-to-end parse→metrics on a `Salary ($)` CSV computes the real total; confirmed
backend↔frontend alignment (`cost_analysis.total_cost` → diagnostics metric `total_cost` →
`Diagnostics.tsx` TOTAL COST tile). PAX baseline unchanged (6,620,000).
**Gate:** PASS — **114 backend tests + clean frontend build**, zero regressions.

---

## 2026-06-16 — Bugfix session (D15): file downloads returned "Not authenticated"

**Reported:** Eric clicked "Download instrument (.xlsx)" and got `{"detail":"Not authenticated"}`.
**Diagnosis:** D13 gates every `/api/v1/*` feature router with `Depends(require_auth)` (Bearer header).
Four UI spots opened files by browser-direct navigation, which can't attach the header → 401:
desire-pulse instrument (`<a href>`), transition register (`<a href>`), deliverable download
(`<a href>`), Settings brand-logo preview (`<img src>`).
**Fix (frontend-only, additive):**
- `services/api.ts`: added `authedBlob()` + `downloadBlob()` (fetch with `Authorization: Bearer` →
  blob → object-URL save). Replaced `pulseInstrumentUrl`/`transitionRegisterUrl`/
  `deliverableDownloadUrl`/`brandLogoUrl` with `downloadPulseInstrument`/`downloadTransitionRegister`/
  `downloadDeliverable(id, filename)`/`brandLogoObjectUrl()`.
- Call sites: ValidationQueue, TransitionPlanner, Deliverables now use buttons; Settings renders the
  logo from a fetched object URL (revoked on change).
- Backend untouched — auth stays header-only (no token-in-URL, per privacy posture).
**Verification:** no frontend test runner, so proven via clean `npm run build` + a TestClient check on
the gated endpoint (401 without header; auth passes with a valid token, then 404 for the demo dataset).
**Gate:** PASS — **114 backend tests + clean frontend build**, zero regressions.

---

## 2026-06-16 — Fix session (D16): queue legibility + Workflow Mapper steps/matrix

**Reported (3):** (1) validation queue feels full of duplicates; SkillsFuture (SFw) data seems missing.
(2) Workflow Mapper steps don't register on "Add step". (3) AI opportunity matrix disconnected from the
selected tasks/step/process.
**Diagnosis:** (1) Not real dups — distinct tasks rendered identical labels (no task text shown) and
the benchmark label hardcoded "O*NET" though SFw is the seeded default; a marketing dataset matches
nothing in the illustrative air-transport seed, so all benchmarks are EXTRA (conf 0) / scores L0
robotics levers. (2) Backend step CRUD/linking is correct (covered by tests) but the frontend never
listed steps — it held only the latest stepId with no visible list or counts. (3) Matrix backend
aggregates correctly, but the UI showed bare L0–L3 with no task tie-back; with the broken step UX
fewer tasks linked than intended.
**Fix (additive):**
- Backend: `validation_service.get_queue` adds `task_text` and a real-source benchmark label; new
  `GET /workflows/{process_id}/steps` + `workflow_service.list_steps` (steps with `linked_tasks`).
- Frontend: ValidationQueue shows task text as the primary ITEM line; WorkflowMapper lists/selects
  steps with counts, confirms add/link, and the matrix shows per-level evidencing task text + a
  no-links warning.
**Tests:** +3 backend (queue task_text+source; steps list/counts; matrix sum == linked) and an e2e
reproducing the marketing scenario (6 identical labels → 6 distinct task_text; steps count=2;
matrix sum=2 with evidencing). Backend↔frontend routes verified aligned.
**Gate:** PASS — **117 backend tests + clean frontend build**, zero regressions.

---

## 2026-06-16 — Product refocus (D17): park scenario simulator; HAS (H0–H5) as headline

**Trigger:** Eric reflected that the app does too much by squeezing in the scenario planner; he wants
focus on role→task breakdown and AI-potential (H0–H5) with benchmark insights. Chosen via
AskUserQuestion: surface the WORKBank Human Agency Scale; hide Scenario+Transition behind a flag; keep
Diagnostics + Workflow Mapper as supporting.
**Changes (additive / reversible):**
- `App.tsx`: `SHOW_SIMULATION=false` removes Scenario Studio + Transition Planner from the nav; pages,
  routes, services, tables and tests all retained (re-enable = one line).
- `task_intelligence_service`: `human_agency_band()` + `HUMAN_AGENCY_SCALE` rubric; rollup buckets gain
  an `agency` H0–H5 breakdown (H0 = no overlay); rollup payload ships the rubric.
- `validation_service`: ai_score rows lead with the H band + carry `has_level`.
- Frontend: Task Intelligence headlines the H0–H5 chart + rubric legend (L0–L3 demoted to supporting);
  RollupBucket/RollupResult types extended.
- Direction (from seed): lower H = more AI-amenable (GREEN=H2, RED=H4). L0–L3 retained internally.
**Tests:** +1 unit (band mapping); extended rollup (agency sums, rubric keys) and queue (band, has_level).
**Open for Eric:** confirm H0 def/direction; optional Workflow-matrix re-band to H0–H5; optional
Deliverables slim. **Gate:** PASS — 118 backend tests + clean frontend build, zero regressions.

---

## 2026-06-16 — Workflow Mapper UX (D18)

Eric's review raised: no run-progress on the matrix; no visible mapped-coverage output; and a question
on process/step semantics.
- Backend: `list_steps` now returns `linked_task_ids` per step (additive; count retained).
- Frontend: matrix "Run" shows a "Running…" button + spinner; new full-width **Mapping coverage** card
  (progress bar + linked/unlinked/empty-step tiles + "what's left"/"what's missing" lists), no API key
  needed. Processes card now explains processes/steps are authored labels onto which CSV-derived tasks
  are linked.
- Clarification (recorded in DECISIONS D18): processes/steps are authored in-app; tasks come from the
  CSV and are linked — hybrid by design.
**Tests:** extended `test_steps_listed_with_counts_and_matrix_reflects_linked_count` to assert
`linked_task_ids`. **Gate:** PASS — 118 backend tests + clean frontend build, zero regressions.

---

## 2026-06-16 — Workflow Mapper matrix re-banded to H0–H5 (D19)

For consistency with the D17 headline, the AI-opportunity matrix now presents the WORKBank Human Agency
Scale (H0–H5) instead of L0–L3. Backend adds `agency_matrix` / per-step `agency_counts` /
`agency_evidencing` / `human_agency_scale` (L0–L3 retained internally); frontend headlines H0–H5 with a
rubric tooltip. Extended the matrix test; live smoke confirmed (L3 tasks → H2, sum == linked).
**Gate:** PASS — 118 backend tests + clean frontend build, zero regressions; tsc clean; keys aligned.

---

## 2026-06-16 — Visual Workflow & Task-analysis Mapper integrated (D20)

Integrated Eric's drag-to-remap board package (Flow / Landscape / Roll-up, hover role-trace, undo,
inspector), refined so the per-task headline is the Human Agency Scale (H0–H5) — consistent with
D17–D19 — with L0–L3 kept as a secondary chip.
- Backend (additive, no migration): `board` / `move_task` / `unmap_task` in workflow_service (+`Position`
  import); `GET /{id}/board`, `POST /{id}/move-task`, `POST /{id}/unmap-task` routes. Board rows expose
  real persisted fields + `human_agency_level`/`has_level` + the HAS rubric.
- Frontend: BoardTask/BoardStep/WorkflowBoard types; api.workflowBoard/moveTask/unmapTask; WorkflowMapper
  replaced with the visual board encoded by H0–H5 (cards/filters/legend/landscape/roll-up); HAS-weighted
  AI opportunity index; L0–L3 as secondary detail in the inspector.
- Tasks flow in from the org CSV via Task Intelligence (board reads persisted data, no API key needed);
  drag persists via move/unmap.
**Tests:** test_workflow_board.py (3, asserting H0–H5 + rubric). **Gate:** PASS — 121 backend tests +
clean frontend build; tsc clean; backend↔frontend aligned; zero regressions.

---

## 2026-06-16 — Drop scenario deck; focus Deliverables (D21)

Frontend-only, consistent with D17. Centralized `SHOW_SIMULATION` into `src/config.ts` (imported by
App.tsx + Deliverables.tsx). The scenario-comparison deck (`PPTX_SCENARIOS`) and transition register
(`XLSX_TRANSITION`) — plus the scenario selector and the `listScenarios` fetch — are now gated behind it.
Deliverables now offers only Diagnostic deck, AI roadmap, TOM, Metrics pack. Backend generators/routes
left intact (reversible). **Gate:** PASS — 121 backend tests + clean frontend build; tsc clean.

---

## 2026-06-16 — Finalized workflow deliverable (D22)

Added `PPTX_WORKFLOW` ("Finalized workflow (.pptx)"): per engagement process, builds a slide from the
real `workflow_service.board` data — steps with their mapped tasks (`text [role · H-band]`), the
per-step H0–H5 mix, and a mapped/unmapped line — plus the standard provenance/caveats slides. Registered
backend (`_EXT`/`_GENERATORS`, `DELIVERABLE_TYPES`) and surfaced as a frontend button.
**Tests:** all-types now 7; new test_workflow_deliverable_reflects_mapping; live deck-content smoke.
**Gate:** PASS — 122 backend tests + clean frontend build; tsc clean; backend↔frontend aligned.

---

## 2026-06-16 — Reset board, engagement deletes, honest classification (D23)

Three review fixes. (1) Reset board now clears all mappings via POST /workflows/{id}/reset-board (active
when mapped_count>0); Undo stays session-scoped. (2) delete_dataset/delete_client + thorough engagement
purge with DELETE routes for client/engagement/dataset and ✕ buttons in the Engagements UI. (3) Scoring
splits no-overlay into ROBOTICS_GSE_LEVER (matched-but-no-overlay physical) vs NO_BENCHMARK_MATCH (no
match at all) so marketing knowledge work is no longer mislabeled as robotics; queue label + H0 rubric
clarified; AIOpportunityResult gains `unclassified`.
**Tests:** +5; live marketing smoke (robotics 0). **Gate:** PASS — 125 backend tests + clean build; tsc clean.

---

## 2026-06-16 — Robust AI benchmarking via Claude + WORKBank HAS rubric (D24)

Determined that live external taxonomy APIs are the wrong fit (WORKBank is static; O*NET/ESCO add
keys/latency/licensing; full datasets break the 200MB guardrail). Instead, benchmark unmatched tasks
with Claude grounded in the WORKBank Human Agency Scale rubric — additive, provenance-gated.
- Backend: infer_unmatched_potential + POST /task-intel/infer-potential (scores NO_BENCHMARK_MATCH rows
  via the HAS rubric; model-inferred/unreviewed → export-blocked; idempotent).
- Frontend: api.inferPotential + AIInferResult; pipeline now extract→benchmark→ai-opportunity→
  infer-potential→rollup; AIOpportunityResult gains `unclassified`.
**Tests:** new rubric-inference test (marketing → H2/GREEN_LIGHT, unreviewed, idempotent).
**Gate:** PASS — 126 backend tests + clean frontend build; tsc clean; aligned; no regressions.

---

## 2026-06-16 — WORKBank integration path + robotics-lever fix (D25)

WORKBank's per-task tables live on Hugging Face (not the GitHub repo, and HF is not allowlisted here), so
real values can't be pulled from the sandbox. Built the integration mechanism instead:
scripts/build_workbank_overlay.py (CSV→overlay, fuzzy columns, O*NET-SOC aggregation) + an additive
taxonomy_loader hook that loads workbank_overlay.curated.json as the authoritative overlay when present.
Also fixed lingering robotics levers: infer-potential now re-bands auto-assigned ROBOTICS_GSE_LEVER rows
via the HAS rubric (keeps genuine physical; idempotent via a rationale tag).
**Tests:** +2 (robotics correction, curated-overlay load). **Gate:** PASS — 128 backend tests + clean build; tsc clean.

---

## 2026-06-16 — WORKBank ingestion hardened + benchmark source-mix (D26)

HF still not allowlisted in the sandbox (403), so live tables can't be pulled here. Made the converter an
importable, unit-tested module (app/services/workbank_ingest.build_overlay_from_dir; CLI is now a thin
wrapper) and verified it offline with synthetic WORKBank-shaped CSVs. Added rollup `source_mix`
{overlay/ai_inferred/robotics/unclassified} + a Task Intelligence "Benchmark coverage" card so reliance on
inference is measurable. Proved overlay-backed tasks bypass inference (source=WORKBank).
**Tests:** +2 (converter aggregation, overlay-bypasses-inference + source_mix). **Gate:** PASS — 130 backend
tests + clean build; tsc clean; aligned.

---

## 2026-06-16 — WORKBank clone as git-ignored build input (D27)

Recommendation: clone the HF dataset into ./workbank as a build input, git-ignored — commit only the
curated overlay subset (A4). Added /workbank/ + /workbank_csv/ to .gitignore; the converter now finds the
CSVs recursively (handles the HF nested layout) and --src defaults to ./workbank. HF clone still blocked
in sandbox (403). **Tests:** +1 (nested layout) + gitignore guard. **Gate:** PASS — 131 backend tests + clean build; tsc clean.

---

## 2026-06-16 — Real WORKBank overlay embedded (D28)

Eric uploaded the WORKBank CSVs. Built + committed the curated overlay
(backend/app/resources/taxonomies/workbank_overlay.curated.json, 104 occupations, 32 KB) via the
hardened converter (handles "Automation Capacity Rating", multi-rater averaging, drops un-surveyed
occupations so they fall to inference). Loader auto-promotes it; tests made hermetic via an autouse
fixture so the committed overlay doesn't shadow the air-transport seed fixtures; +1 real-file load test.
Verified end-to-end: a marketing task now scores from the WORKBank overlay (source=WORKBank), no inference.
Raw dataset stays git-ignored. **Gate:** PASS — 132 backend tests + clean build; tsc clean.
