# Build Specification — OrgAI Advisory Workbench

**Target codebase:** `advisory-workbench` (NEW greenfield repo)
**GitHub remote:** `https://github.com/Kaizen74/AI-Org-Advisory-Workbench` — connect as `origin` in Phase 0; push after every commit (see A2). The repo MUST be **private**: it will contain client-derived organizational data during development.
**Executor:** Claude Code
**Version:** v1.2
**Changelog v1.2:** GitHub remote integration (push-on-commit for off-machine memory resilience), data-hygiene `.gitignore` rules, and a binding README specification (B7) requiring non-technical, click-by-click run and deploy instructions, maintained from Phase 0 onward.
**Changelog v1.1:** Companion files (`taxonomy_seed.starter.json`, `WORKFORCE_INTELLIGENCE_ARCHITECTURE.md`) confirmed and integrated: B0 now specifies their placement, the loader's `desire_score → desire_score_us` mapping, confidence-thresholded validation routing, and the architecture decisions to carry into `DECISIONS.md`.
**Companion documents (all must be in the repo root before Phase 0):**
1. `PRD_AI_Transformation_Advisory_Workbench.md` (v1.2) — the product requirements (the *what and why*; this spec is the *how*).
2. `taxonomy_seed.starter.json` — reference-data starter; its `_meta` warnings are binding.
3. `WORKFORCE_INTELLIGENCE_ARCHITECTURE.md` — legacy WI module architecture; read in Phase 0 (see B0 for which decisions carry over and which do not).

> **How to use this document.** Part A is the *operating protocol* — non-negotiable rules for how
> Claude Code must work on this codebase: persistent memory across interrupted sessions, micro-task
> checkpointing, mock testing, and regression safety. Part B is the *requirement specification*.
> Claude Code must read and internalise Part A **before writing any code**, copy Part A into a
> root-level `CLAUDE.md` as its very first action (Phase 0, Task 0.1), and obey it for the entire
> engagement. Sessions WILL be interrupted without warning by plan limits — the protocol assumes
> every session can end mid-task and is designed so the next session resumes losslessly.

---

# PART A — OPERATING PROTOCOL FOR CLAUDE CODE (MANDATORY)

This is a greenfield build executed by a non-technical product owner (Eric) across many short
Claude Code sessions that may be **cut off abruptly by plan limits**. The two existential risks
are: (1) losing context between sessions, and (2) silently breaking something that already worked.
Every rule below targets one of those two risks.

## A1. Persistent memory & interruption resilience

The repo IS the memory. Nothing important may live only in the conversation.

**Memory files (create in Phase 0, maintain forever):**

- **`CLAUDE.md`** (repo root): contains this entire Part A plus a one-paragraph current-state
  summary (updated each session end). Claude Code auto-loads this file every session.
- **`PROGRESS.md`** (repo root): append-only build journal. One dated entry per completed phase
  AND per session. Never rewrite history.
- **`.checkpoints/LATEST.md`**: the single source of truth for "where are we." Overwritten
  constantly (see A2). Structure:

  ```markdown
  # LATEST CHECKPOINT
  **Updated:** <ISO datetime>
  **Phase:** P<n> — <name>
  **Last completed micro-task:** <task id + one line>
  **In-flight micro-task:** <task id, exact file(s) being edited, what is half-done, what remains>
  **Next action (be exact):** <e.g. "Add zone classification test in backend/tests/test_ai_scores.py, then implement classify_zone() in services/task_intelligence_service.py">
  **Test status:** <last full-gate result: PASS/FAIL + count>
  **Recovery commands:** cd backend && pytest tests/ -v ; cd ../frontend && npm run build
  **Open questions for Eric:** <list or "none">
  ```

- **`.checkpoints/BASELINE.md`** + **`backend/tests/baseline/`**: the golden baseline — the list
  of passing tests and snapshot fixtures that must never regress (grows each phase; see A3).
- **`.checkpoints/DECISIONS.md`**: append-only log of design decisions and their rationale, so a
  future session never re-litigates or accidentally reverses a settled choice.

**Micro-task granularity (the plan-limit defence):**
- Decompose every phase into micro-tasks of **≤ 30 minutes** each, written as a checklist at the
  top of the phase's section in `PROGRESS.md` before starting the phase.
- **After EVERY completed micro-task** (not just at session end): (1) run the relevant tests,
  (2) `git commit` (A2), (3) update `LATEST.md`. This means an abrupt cut-off can only ever lose
  one partial micro-task, and `LATEST.md` describes exactly how to finish it.
- Never start a micro-task you suspect cannot finish in the current session's remaining budget;
  instead, write its plan into `LATEST.md` "Next action" and stop cleanly.

**Session-start ritual (every session, no exceptions):**
1. Read `CLAUDE.md`, `.checkpoints/LATEST.md`, `.checkpoints/DECISIONS.md`, and the current
   phase section of `PROGRESS.md`.
2. Run `git log --oneline -15` and `git status` — trust the repo over memory; if there are
   uncommitted changes, reconcile them against `LATEST.md`'s in-flight block before anything else.
3. Run the regression gate (A3) to confirm a clean start. If red, fixing the red IS the first task.
4. State in one sentence the phase and micro-task being resumed — then proceed.

**Session-end ritual (also applies when running low — do this EARLY, not at the last token):**
1. Finish or cleanly park the in-flight micro-task (a parked task = code compiles, tests for
   completed work pass, partial work is committed with a `wip:` prefix).
2. Run the full regression gate. Do not end on red without recording exactly what is red and why
   in `LATEST.md`.
3. Update `LATEST.md` (full structure above), append a session entry to `PROGRESS.md`, update the
   one-paragraph summary in `CLAUDE.md`, append any decisions to `DECISIONS.md`.
4. Final commit.

## A2. Git & coding continuity

- Initialise git in Phase 0 and connect the remote:
  `git remote add origin https://github.com/Kaizen74/AI-Org-Advisory-Workbench.git`.
  **Push after every commit** (`git push origin <branch>`). The GitHub copy is the off-machine
  backup of the build memory (`CLAUDE.md`, `.checkpoints/*`, `PROGRESS.md`) — a session cut-off
  AND a laptop failure together still lose at most one micro-task. If a push fails (offline,
  auth), record it in `LATEST.md` and retry at the next opportunity; never let unpushed commits
  accumulate past one session.
- **Data hygiene (`.gitignore`, created in Phase 0):** never commit `*.db` / `*.sqlite*`, `.env`,
  any client CSV or upload directories (`backend/uploads/`), or generated deliverables
  (`backend/output/`). Only the synthetic PAX fixture and the taxonomy seed are allowed data files
  in the repo. A phase-close check: `git ls-files` contains no real client data.
- Work on `main` until P1 completes, then a branch per phase:
  `feat/p2-task-intelligence` etc., merged to `main` only when the phase gate is green.
- **Small, reversible commits**, one micro-task each. Message format:
  `p<N>(<module>): <what> — <why>`. Interrupted work: `wip(p<N>): <state> — see LATEST.md`.
- **Never leave the repo in a non-compiling state at a commit**, except `wip:` commits, which must
  be the newest commit only and resolved first thing next session.
- Once a phase is merged, its code is treated as *existing code*: changes to it become
  **additive-only** — no changing public signatures, return shapes, routes, or schema of completed
  modules without writing the reason into `DECISIONS.md` first and adding regression tests proving
  prior behaviour is preserved (or explicitly migrated).

## A3. Mock testing, regression gates & unintended-consequence checks

This is the heart of the protocol. Follow it literally.

**Rule 1 — Mock the Claude API everywhere, from day one.** No test may make a real network call.
In Phase 0 create a pytest fixture `mock_claude` (in `backend/tests/conftest.py`) that
monkeypatches the Anthropic client so `messages.create(...)` returns canned objects whose
`.content[0].text` is fixed, valid JSON loaded from `backend/tests/fixtures/*.json`. Every
AI-touching test uses it. Tests must run **offline, deterministic, and free**.

**Rule 2 — The golden baseline grows with the build.** At the end of every phase:
- Append the phase's passing test list to `.checkpoints/BASELINE.md`.
- Snapshot key outputs as fixtures under `backend/tests/baseline/` — minimum set:
  - P1: full metrics payload for the PAX fixture CSV (must match v1 values: total_employees=64,
    total_managers=16, manager_ratio_pct=25.0, total_cost=5770000, organizational_layers=6).
  - P2+: one canonical response per new GET endpoint (shape + values, with mocked AI).
  - P4+: scenario delta payload for a fixed move sequence on the PAX fixture.
- Add a parity test asserting current output == snapshot, byte-stable for deterministic fields.

**Rule 3 — The regression gate.** One command, run: at session start, after every phase, after
**every bug fix**, and at session end:
```bash
cd backend && pytest tests/ -v && cd ../frontend && npm run build
```
The gate passes only if: (a) every test in `BASELINE.md` still passes — no prior test removed,
skipped, or weakened; (b) all new tests pass; (c) all baseline snapshots match; (d) the frontend
builds with zero TypeScript errors. Wire it as `make gate` (or `scripts/gate.sh`) in Phase 0 so
it is one command.

**Rule 4 — Fix protocol (regression-proofing every fix).** Any bug fix, however small, follows:
1. Write a failing test that reproduces the bug FIRST.
2. Implement the minimal fix.
3. Run the FULL gate (not just the new test) — a fix is not done until the entire suite and all
   baseline parity checks are green, proving no unintended consequence elsewhere.
4. Commit as `fix(p<N>): <bug> — adds regression test <file>::<test>`.

**Rule 5 — Unintended-consequence checklist (assert at every phase close):**
- All Alembic migrations are additive within a phase and reversible (`downgrade()` drops only
  what the phase added). Completed-phase tables are never altered destructively.
- `main.py` changes are limited to `include_router` lines and startup config.
- No router prefix, existing route, or CORS config of a completed phase changed.
- No heavy ML dependency added (`torch`, `transformers`, `sentence-transformers` are banned).
- Provenance fields (`source`, `confidence`, `review_state`) are present on every AI-derived row —
  a test asserts this on the canonical pipeline output.

**Rule 6 — Test-first for pure logic.** For deterministic functions (metric formulas, zone
classification, rollup aggregation, scenario move apply/undo, delta computation, anonymization
hashing), write tests before implementation.

## A4. Hard guardrails

- **Claude API only** for inference; model strings come from env config (`MODEL_EXTRACT`,
  `MODEL_SYNTH`) with sensible defaults — never hardcoded in service code.
- **Deployment budget:** repo stays Vercel/Railway-friendly (~200MB); only curated taxonomy
  subsets are committed, never full O*NET/SFw/ESCO datasets.
- **Provenance transparency is a correctness requirement:** every benchmark/score carries
  `source` ∈ {`SFw`, `ONET`, `WORKBank`, `consultant-approved`, `model-inferred`} and
  `review_state` ∈ {`unreviewed`,`approved`,`edited`,`rejected`}. Deliverable exports must exclude
  or banner `unreviewed` model-inferred content (PRD M6).
- **WORKBank guardrails (binding; restated from the seed's `_meta`):** `desire_score_us` is US
  worker preference — label it as such everywhere; local desire is a separate field, never
  overwritten. `has_level` and `capability_score` are independent — never collapsed. Physical
  tasks (e.g., ramp handling) get no software-agent overlay; tag `model-inferred` and surface as a
  robotics/GSE lever. All starter WORKBank values are ILLUSTRATIVE; the O*NET codes are
  occupation-level and must be verified/refined before client use — every payload's `caveats[]`
  must say so until they are.
- **Ask, don't assume:** if a requirement is ambiguous or two PRD clauses conflict, write the
  question into `LATEST.md` "Open questions for Eric", choose the most conservative interpretation
  if blocked, and record the choice in `DECISIONS.md`.

---

# PART B — REQUIREMENT SPECIFICATION

## B0. Stack, layout, legacy assets & companion files

**Stack (same as v1 — proven):** FastAPI + async SQLAlchemy + SQLite (Postgres-ready models) +
Alembic; React + Vite + TypeScript + Tailwind + Recharts; Anthropic Python SDK.

**Repo layout:**
```
advisory-workbench/
├── CLAUDE.md  PRD_...md  BUILD_SPEC_...md  PROGRESS.md
├── docs/           (WORKFORCE_INTELLIGENCE_ARCHITECTURE.md moves here in P0)
├── .checkpoints/   (LATEST.md, BASELINE.md, DECISIONS.md)
├── legacy/         (read-only copy of the v1 app — Eric places this; DO NOT import as a package,
│                    PORT files from it per phase instructions)
├── backend/        (app/{api,models,services,parsers,resources}, alembic/, tests/, scripts/)
└── frontend/       (src/{pages,components,services,types})
```

**Assets to PORT from `legacy/` (copy + adapt, with tests):**
- `metrics_service.py` (P1 — adapt to ID-keyed graph and typed persistence)
- `csv_parser.py` (P1 — adapt: key on Employee ID with surrogate-key fallback; duplicate-name
  validation warning)
- `archetypes_reference.py` (P1 — port unchanged)
- `work_activities_service.py` JSON parse/repair helpers (P0 — extract into
  `backend/app/services/_json_utils.py`)
- `backend/tests/fixtures/` PAX CSV + expected metrics (P0 — this is baseline fixture #1)

**Companion files Eric places in the repo root (confirmed available — do NOT reinvent):**
- `taxonomy_seed.starter.json` → move to `backend/app/resources/taxonomies/` in P2. Its `_meta`
  block is **binding** (see A4). **Loader field mapping:** seed `desire_score` →
  `desire_score_us` column (the schema's dual-score design); `desire_score_local` starts NULL and
  is populated only by the M2 pulse instrument. Upsert by natural keys: `code` (sources),
  `task_ref` (tasks), `onet_task_code` (overlay).
- `WORKFORCE_INTELLIGENCE_ARCHITECTURE.md` → move to `/docs`. **Read it in Phase 0.** Record two
  of its decisions in `DECISIONS.md` as carried over: (1) the AI overlay is joined to tasks
  *logically* by `onet_task_code`, never a hard FK, so the overlay stays independently replaceable
  when real WORKBank pulls arrive; (2) the three-layer separation — reference layer is
  engagement-independent and seeded once; pipeline results cascade under an engagement/dataset;
  presentation reads only persisted results. Also record one decision as **superseded**: its
  "single cross-boundary FK" rule applied to the legacy brownfield app and does NOT apply to this
  greenfield schema, where tasks are first-class rows.
- **Crosswalk confidence drives the validation queue:** any mapping with `confidence < 0.70` —
  including CURATED seed rows (one ships at 0.40) — defaults to `review_state = unreviewed` and
  appears in the M3 queue. Add a test asserting this threshold behaviour.

If `legacy/` or either companion file is missing at Phase 0, STOP and record in `LATEST.md`
exactly what is missing — do not reinvent these assets.

## B1. Data model (summary — implement incrementally per phase)

All tables: uuid string PK via `generate_uuid`, `created_at`; FK cascade within an engagement so
purge is clean. JSON columns only where the structure is genuinely variable (payloads, move
params); analytical values are typed columns.

**Engagement core (P0–P1):**
- `clients` (name, industry, anonymization_default)
- `engagements` (client_id FK, name, strategy_context TEXT, design_criteria TEXT,
  default_taxonomy_code, anonymized BOOL)
- `datasets` (engagement_id FK, version INT, filename, row_count, validation_warnings JSON)
- `positions` (dataset_id FK, employee_key — Employee ID or surrogate, display_name,
  pseudonym NULLABLE, job_title, grade, level INT, manager_key NULLABLE, department, salary FLOAT
  NULLABLE, work_activities TEXT NULLABLE)
- `metric_values` (dataset_id FK, metric_code, scope — org|department, scope_key NULLABLE,
  value FLOAT, unit, computed_at)

**Reference layer (P2 — port WI design; engagement-independent):** `taxonomy_source`,
`taxonomy_task`, `taxonomy_crosswalk` (with `method` ∈ CURATED|MODEL_INFERRED|
CURATED_BY_CONSULTANT), `task_ai_overlay` (onet_task_code idx, has_level 1–5, desire_score_us,
capability_score, zone). The overlay has NO hard FK to tasks — logical join by `onet_task_code`
only (carried-over architecture decision).

**Task intelligence (P2–P3):**
- `tasks` (position_id FK, task_text, batch_id, extraction_source)
- `task_benchmarks` (task_id FK, taxonomy_source_code, status ∈ MATCHED|MISSING|EXTRA,
  matched_taxonomy_task_id NULLABLE FK, onet_task_code NULLABLE, source, confidence FLOAT,
  review_state, reviewed_at NULLABLE)
- `task_ai_scores` (task_id FK, has_level NULLABLE, zone NULLABLE, desire_score_us NULLABLE,
  desire_score_local NULLABLE, capability_score NULLABLE, ai_opportunity_level ∈ L0–L3,
  rationale TEXT, source, confidence, review_state, reviewed_at NULLABLE)
- `desire_pulse_responses` (engagement_id FK, task_ref, respondent_hash, desire_rating INT 1–5)

**Design & delivery (P4–P7):**
- `scenarios` (engagement_id FK, dataset_id FK, name, status ∈ DRAFT|PRESENTED, parent_scenario_id
  NULLABLE — fork lineage)
- `design_moves` (scenario_id FK, seq INT, move_type ∈ MERGE_UNITS|SPLIT_UNIT|REPARENT|
  DELETE_POSITION|ADD_POSITION|CHANGE_GRADE|REASSIGN_TASKS|SET_ANCHOR_LAYER|SET_DOCKING_STATION,
  params JSON, rationale TEXT, activator_tag NULLABLE 1–5)
- `scenario_metrics` (scenario_id FK, metric_code, value, delta_vs_baseline)
- `processes` (engagement_id FK, name, value_stream) / `process_steps` (process_id FK, seq, name)
  / `task_links` (process_step_id FK, task_id FK)
- `deliverables` (engagement_id FK, type ∈ PPTX_DIAGNOSTIC|PPTX_SCENARIOS|PPTX_AI_ROADMAP|
  DOCX_TOM|XLSX_METRICS|XLSX_TRANSITION, file_path, provenance_summary JSON, generated_at)
- `audit_events` (engagement_id FK, event_type, detail JSON, at)

## B2. Backend services & API (per phase)

Conventions carried from v1: routers under `/api/v1/...`, async session dependency
`get_session`, `claude_service` singleton consumed (never modified) by feature services, strict
JSON prompts parsed via `_json_utils`, guard pattern (404 no dataset, 400 no API key for AI
endpoints; non-AI endpoints must work with no key).

| Module | Service | Router prefix | Key endpoints |
|---|---|---|---|
| Engagement Hub | `engagement_service` | `/api/v1/engagements` | CRUD clients/engagements; `POST /{id}/datasets` (CSV upload→parse→persist positions+warnings); `DELETE /{id}/purge` |
| Diagnostics | `diagnostics_service` | `/api/v1/diagnostics` | `POST /compute` (dataset_id) → typed `metric_values`; `GET /summary`; `GET /archetypes`; `GET /activator-screen` |
| Task Intelligence | `task_intelligence_service` | `/api/v1/task-intel` | `POST /extract` (batched per department/~40 positions, parallel, deterministic merge); `POST /benchmark`; `POST /ai-opportunity`; `GET /rollup`; `GET /quick` (no API key) |
| Validation | `validation_service` | `/api/v1/validation` | `GET /queue?filter=confidence<x`; `POST /review` (bulk approve/edit/reject → updates review_state, writes CURATED_BY_CONSULTANT crosswalk rows); `GET /stats` |
| Desire pulse | (in task_intel) | `/api/v1/task-intel/pulse` | `GET /instrument.xlsx` (export top-N tasks); `POST /responses` (xlsx/CSV import → desire_score_local recompute) |
| Scenarios | `scenario_service` | `/api/v1/scenarios` | CRUD; `POST /{id}/moves`; `DELETE /{id}/moves/{seq}` (undo = recompute from baseline + remaining moves); `GET /{id}/delta`; `GET /compare?ids=a,b,c`; `POST /{id}/present` (locks; edits fork) |
| Workflow Mapper | `workflow_service` | `/api/v1/workflows` | process CRUD; `POST /map-tasks`; `POST /opportunity-matrix` (L0–L3 per process, AI) |
| Transition | `transition_service` | `/api/v1/transition` | `POST /compute` (impact classes per scenario); `GET /register`; skill-gap → SFw pathway suggestions routed through validation queue |
| Deliverables | `deliverable_service` | `/api/v1/deliverables` | `POST /generate` (type, template); `GET /list`; export blocks/banners unreviewed model-inferred content; auto-generates provenance disclosure page |

**Scenario engine determinism (critical):** `apply_moves(baseline_positions, moves)` is a pure
function. Property test: applying then removing any move sequence reproduces baseline metrics
byte-identically. Deltas computed against `metric_values`, not re-parsed CSV.

**Anonymization (P7 but design-in from P1):** when engagement.anonymized, `pseudonym` is generated
at ingest (stable salted hash), all API responses and exports use pseudonyms, real names live only
in `positions.display_name` and are excluded from deliverables; purge endpoint nulls them.

## B3. Frontend (per phase)

Mirror v1 ergonomics (API-key gate, quick stats, run buttons, collapsible sections,
loading/empty/error states). Pages:
`Engagements` (P1), `Diagnostics` (P1), `TaskIntelligence` (P2), `ValidationQueue` (P3 — table
with confidence filter, bulk approve/edit/reject, source badges), `ScenarioStudio` (P4 — move
builder + live delta panel + 3-way comparison view), `WorkflowMapper` (P5), `TransitionPlanner`
(P5), `Deliverables` (P6), `Settings`. Recharts visuals: desire×capability zone scatter (US vs
local toggle), HAS distribution bars with department filter, L0–L3 breakdown, scenario delta
bars, benchmark table with provenance badges, caveats callout on every AI page.

## B4. Phased delivery plan (each phase ends with the A3 gate + checkpoint updates)

- **P0 — Protocol & scaffold.** git init + connect `origin`
  (https://github.com/Kaizen74/AI-Org-Advisory-Workbench, private) + `.gitignore` per A2; write
  `CLAUDE.md` (Part A), `.checkpoints/*`, `PROGRESS.md`, and the **README stub per B7**; verify
  `legacy/` AND both companion files present; move the architecture doc to `/docs` and read it
  (record the carried-over + superseded decisions in `DECISIONS.md`); scaffold backend+frontend
  skeletons that run; `mock_claude` fixture + `_json_utils` port + PAX fixture in place;
  `scripts/gate.sh`. First push to GitHub. Gate.
- **P1 — Engagement core + diagnostics.** Migration 001 (engagement core tables); CSV parser port
  with **Employee-ID keying + duplicate-name warning test**; metrics engine port to typed
  `metric_values` with **PAX parity test**; archetype port; activator pre-screen; Engagements +
  Diagnostics pages. Gate (baseline now includes PAX parity).
- **P2 — Task intelligence.** Migration 002 (reference + task tables); seed loader (idempotent
  upsert from `taxonomy_seed.starter.json`, with the `desire_score → desire_score_us` mapping and
  a loader test against the starter file); batched extract/benchmark/ai-opportunity pipeline with
  mocked-AI tests including a **500-position synthetic fixture** proving batching+merge; rollups;
  TaskIntelligence page; provenance-presence test; caveats include the O*NET occupation-level
  granularity flag. Gate.
- **P3 — Validation queue + local desire.** Review endpoints + page; **confidence<0.70 →
  unreviewed routing test (must catch the seed's 0.40 crosswalk row)**; crosswalk learning
  (CURATED_BY_CONSULTANT); pulse export/import + dual desire scores; test: unreviewed items
  excluded from canonical "client-ready" payload. Gate.
- **P4 — Scenario Studio.** Migration 003; pure move engine with **apply/undo byte-parity
  property test**; delta + 3-way comparison endpoints; ScenarioStudio page; present/lock/fork.
  Gate (baseline adds scenario-delta snapshot).
- **P5 — Workflow Mapper + Transition Planner.** Migration 004; process/task linking; L0–L3
  opportunity matrix per process (mocked-AI tests); impact classes + SFw pathway suggestions via
  validation queue; both pages; transition register xlsx export. Gate.
- **P6 — Deliverable Factory.** python-pptx/docx/openpyxl generators; SATS-brand template first,
  generic second; provenance disclosure page auto-generated; export-block test for unreviewed
  content; Deliverables page. Gate.
- **P7 — Security & deploy.** Anonymization end-to-end test (no real name in any export);
  purge + audit log; env-config hardening; Postgres compatibility check; **finalize the README
  per B7 and verify it by following it verbatim**; deploy to Vercel + Railway and capture every
  click/step taken into the README's deploy section. Final gate + final checkpoint + final push.

## B5. Acceptance criteria (definition of done)

1. Full gate green; every `BASELINE.md` test passing; PAX metrics identical to v1 values.
2. All AI tests mocked; suite runs offline and deterministically.
3. Every AI-derived row carries `source`, `confidence`, `review_state`; canonical payload test
   enforces it; deliverables exclude/banner unreviewed model-inferred content.
4. Seed loader is idempotent against `taxonomy_seed.starter.json`; the dual-desire mapping is
   correct; the confidence<0.70 routing test passes on the starter's 0.40 row; payload caveats
   carry the WORKBank-illustrative and O*NET-granularity flags.
5. Scenario apply/undo byte-parity test passes; 3-way comparison works on the PAX org.
6. Duplicate-name dataset parses with warning and intact tree (ID-keyed graph).
7. One-click SATS-branded diagnostic pptx generated from live PAX data.
8. Anonymized engagement leaks no real name in any API response or export; purge works.
9. `CLAUDE.md`, `PROGRESS.md`, `LATEST.md`, `DECISIONS.md`, `BASELINE.md` current at close.
10. README meets the full B7 specification and has been verified by following it verbatim from a
    clean state (local run AND cloud deploy); `git ls-files` on the GitHub repo contains no
    database files, `.env`, client CSVs, or generated deliverables; all commits are pushed.

## B6. Out of scope for v1 (record, do not build)

Local embedding models (TechWolf et al.); full O*NET/SFw/ESCO ingestion (including task-statement
level WORKBank refinement — record as the first data upgrade); HRIS API integrations; real-time
co-editing; automated ONA/calendar ingestion.

## B7. README specification (binding — the GitHub front page for a non-technical owner)

The repo README at https://github.com/Kaizen74/AI-Org-Advisory-Workbench is written for **Eric, a
non-technical owner** — not for developers. Create a stub in P0, keep it current at every phase
close (add what shipped), finalize in P7. Quality bar: **Eric can go from a fresh computer to a
running app, and from the repo to a live cloud deployment, by following the README alone, without
asking anyone what a command means.**

Required structure:

1. **What this app is** — three sentences, plain language: what it does, who it's for, what the
   modules are (one line each as they ship).
2. **Before you begin (one-time installs)** — exactly what to install and how, with download
   links and what to click: Git (or GitHub Desktop), Python 3.11+, Node.js LTS. State how to
   verify each install worked (the exact command to type and what a good answer looks like).
3. **Run the app on your own computer** — numbered steps, every command in a copy-paste block,
   each with one plain-language line saying what it does and what success looks like
   (e.g., "you should see `Uvicorn running on http://127.0.0.1:8000` — leave this window open").
   Two terminals (backend, frontend) explained explicitly; the URL to open; where to enter the
   Anthropic API key (with a link to where to create one).
4. **Deploy to the cloud (Vercel + Railway)** — click-by-click with the actual button names and
   screens encountered during the P7 deployment: connect GitHub repo → import project → set the
   environment variables (list each variable, what it is, where its value comes from) → deploy →
   the URL to visit. Include how to redeploy after changes (push to `main` → automatic).
5. **Updating the app** — how to pull the latest version locally (or via GitHub Desktop) and
   restart.
6. **If something goes wrong** — a troubleshooting table of the 8–10 most likely failures
   (port already in use, missing API key, `pip`/`npm` not found, database locked, blank page,
   Railway build failure), each with the plain-language fix.
7. **Data & privacy notes** — repo is private; client data never committed; anonymization mode;
   how to purge an engagement.
8. **For developers / Claude Code** — one short section linking to `CLAUDE.md`,
   `BUILD_SPEC_ADVISORY_WORKBENCH.md`, the PRD, and `.checkpoints/LATEST.md` (build state).

Rules: no unexplained jargon (first use of any term like "terminal", "environment variable",
"repository" gets a one-line plain-language explanation); no step may assume prior knowledge;
every command is copy-paste-ready; screenshots optional but section 4 must name actual UI buttons.
