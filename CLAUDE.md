# CLAUDE.md — OrgAI Advisory Workbench

> This file is auto-loaded by Claude Code every session. It contains the **mandatory operating
> protocol (Part A of the Build Spec)** plus a one-paragraph current-state summary that is updated
> at every session end. Read the current-state summary, then obey Part A in full.

---

## CURRENT-STATE SUMMARY (updated each session end)

**As of 2026-06-14 (Phase 6 — COMPLETE):** P0–P6 are done and pushed. P6 shipped: migration 005
(`deliverables`), the modern-minimalist deliverable template (`deliverable_theme`, D10; SATS theme
stubbed pending brand assets), pptx/docx builders, six generators (PPTX diagnostic / scenario
comparison / AI roadmap, DOCX TOM, XLSX metrics / transition register) — each with an auto-generated
**provenance disclosure** (% content by source tag + caveats) and the **export-block** rule
(unreviewed model-inferred content excluded from client content, count disclosed), the
`/api/v1/deliverables` router (generate/list/download; files → gitignored `backend/output/`), and the
frontend Deliverables page. **PAX baseline still LOCKED (D9): 64 / 34 / 53.1% / 6,620,000 / 6.**
**Gate GREEN: 74 backend tests + clean frontend build.** Next: await Eric's go-ahead, then **Phase 7
(Security & deploy)** — see `.checkpoints/LATEST.md`. Do not start P7 until Eric confirms. Completed
P0–P6 code is now **additive-only**.

**Pre-P7 Settings block (2026-06-14 — COMPLETE):** `app_settings` (migration 006) + `settings_service`
+ `/api/v1/settings`: UI-managed Anthropic key (masked), local-LLM provider fallback (D11), swappable
brand logo+palette driving the deck (D12); **SATS brand preconfigured** from Eric's corporate
template (logo committed as a resource; red `EE2536`/Arial).

**As of 2026-06-14 (Phase 7 — CODE COMPLETE; live deploy pending Eric):** All seven phases (P0–P7)
are built and pushed. P7 shipped: end-to-end **anonymization** (salted pseudonyms at ingest;
transition register JSON + xlsx carry no real names — test-enforced), the **audit trail**
(`audit_events`, migration 007; wired into uploads/AI/validation/deliverables/purge; `/api/v1/audit`),
**PDPA real-name purge** + full purge, **Postgres readiness** (asyncpg/psycopg2, `db_url.to_sync_url`,
dialect-compile test) + env hardening (`ANON_SALT`, `CORS_ORIGINS`), a configurable frontend API base
(`VITE_API_BASE_URL`) + Railway `Procfile`, and the finalized **B7 README** (Vercel+Railway deploy
guide, troubleshooting table, privacy). Lifespan startup hydrates the settings cache. **PAX baseline
still LOCKED (D9): 64 / 34 / 53.1% / 6,620,000 / 6.** **Gate GREEN: 100 backend tests + clean frontend
build, zero regressions.** **Remaining (Eric, manual): the live Vercel+Railway deploy and verifying
the README verbatim — needs his accounts + a browser.** All completed code is **additive-only**.

**Private access control added (2026-06-14 — D13):** the app is **not public** — `access_users`
(migration 008) + `access_service` (PBKDF2) + `token_service` (HMAC, stdlib) + an auth gate on every
`/api/v1/*` route except `auth`; neutral login screen; owners manage the email+passcode allowlist in
Settings → Access control; bootstrap from `ACCESS_USERS` env, tokens signed by `AUTH_SECRET`. README
deploy guide updated for private hosting. **Gate GREEN: 108 backend tests + clean frontend build;**
live-verified (401 → login → token → 200). Deploy must set `AUTH_SECRET` + `ACCESS_USERS`.

**Cost-metric bugfix (2026-06-15 — D14):** real uploads showed **TOTAL COST $0** because the CSV
parser matched the salary column on the exact header `"Salary"` while the client export labels it
`"Salary ($)"`. Fixed `OrgCSVParser._find_salary_column` to match any header containing "salary"
(`Salary ($)`, `Salary (USD)`, `Annual Salary`, …); `$`/`,` cleaning and `NA→0` unchanged. PAX baseline
(exact `Salary`) unchanged — still LOCKED 64 / 34 / 53.1% / 6,620,000 / 6. Added 2 regression tests;
backend↔frontend alignment confirmed (`cost_analysis.total_cost` → metric `total_cost` → Diagnostics
tile). **Gate GREEN: 114 backend tests + clean frontend build, zero regressions.**

**Authed-download bugfix (2026-06-16 — D15):** file downloads returned `{"detail":"Not authenticated"}`
because the D13 auth gate (`Depends(require_auth)` on every `/api/v1/*` router) needs a Bearer header
that browser-direct `<a href>`/`<img src>` can't send. Fixed frontend-only: `services/api.ts` gained
`authedBlob`/`downloadBlob` (fetch with token → blob → save); the four affected spots — desire-pulse
instrument, transition register, deliverable download, Settings brand-logo preview — now go through it
(URL-builder methods replaced by `downloadPulseInstrument`/`downloadTransitionRegister`/
`downloadDeliverable`/`brandLogoObjectUrl`). Backend auth kept header-only (no token-in-URL, per privacy
posture); no backend/route/schema change. Verified via clean build + TestClient gate check (401 without
header, auth-passes with token). **Gate GREEN: 114 backend tests + clean frontend build, zero regressions.**

**Queue legibility + Workflow Mapper UX (2026-06-16 — D16):** three reported issues fixed. (1) The
validation queue looked full of duplicates and SFw seemed missing — distinct tasks shared a generic
label and the benchmark label hardcoded "O*NET". `validation_service.get_queue` now attaches `task_text`
and builds the label from the real `taxonomy_source_code` (SFw is the seeded default; nothing matches
the illustrative air-transport seed for a marketing dataset → all `EXTRA`/L0-robotics). (2) Workflow
Mapper steps "didn't register": the UI never listed steps. New `GET /api/v1/workflows/{id}/steps`
(+ `workflow_service.list_steps`) returns steps with `linked_tasks` counts; the page now lists/selects
steps and confirms add/link. (3) The matrix looked disconnected: the card now shows per-level
**evidencing task text** and a no-tasks-linked warning (backend aggregation was already correct).
Additive-only; benchmark-label test still passes. **Gate GREEN: 117 backend tests + clean frontend
build, zero regressions.**

**Product refocus + Workflow Mapper overhaul (2026-06-16 — D17–D20):** (D17) Scenario Studio +
Transition Planner parked behind `SHOW_SIMULATION` (reversible nav flag; code+tests intact); the
**WORKBank Human Agency Scale (H0–H5)** is now the headline AI-potential metric app-wide
(`human_agency_band` + `HUMAN_AGENCY_SCALE`; lower H = more AI-amenable, H0 = no software-agent overlay;
L0–L3 retained internally). (D18) Workflow Mapper matrix run-progress + a mapping-coverage view
(`list_steps` gained `linked_task_ids`). (D19) the AI-opportunity matrix re-banded to H0–H5
(`agency_matrix`/`agency_counts`/`agency_evidencing`/rubric). (D20) integrated the **visual Workflow &
Task-analysis Mapper** — a drag-to-remap board (Flow / Landscape / Roll-up, hover role-trace, undo,
inspector) over new additive endpoints `GET /workflows/{id}/board`, `POST .../move-task`,
`.../unmap-task` (no migration; reuses Position/Task/TaskAIScore/TaskLink); board rows carry real
persisted fields + headline `human_agency_level` (H0–H5, L0–L3 secondary) + the HAS rubric. **Gate
GREEN: 121 backend tests + clean frontend build, zero regressions.**

**Deliverables + robust benchmarking + real WORKBank + Mapper polish (2026-06-16 — D21–D42):**
a large additive run, all on branch `claude/compassionate-knuth-wx5bjq`. Highlights: (D21) dropped the
scenario deck — `SHOW_SIMULATION` centralized in `src/config.ts` (currently **false**). (D22/D32/D33)
the **Finalized-Workflow deliverable** (`PPTX_WORKFLOW`) + Workflow-Mapper `↓CSV`/`↓PPTX` export
(`/workflows/export.csv|.pptx`, `build_workflow_deck`, `export_workflow_csv`); the deck is now a VISUAL
board (step columns, HAS-coloured task cards, arrows). (D23/D30) delete client/engagement/dataset and
process/step (cascade), reset-board, and a new `NO_BENCHMARK_MATCH` zone distinct from
`ROBOTICS_GSE_LEVER` (stop mislabelling unmatched knowledge work as robotics). (D24–D29) **robust AI
benchmarking** — unmatched tasks scored by Claude grounded in the WORKBank HAS rubric
(`infer_unmatched_potential`, `POST /task-intel/infer-potential`; model-inferred → export-blocked) +
benchmark `source_mix` transparency. (D26–D29) the **real WORKBank overlay** embedded
(`workbank_overlay.curated.json`, 104 occupations, built via the hardened `workbank_ingest` converter;
raw dataset git-ignored). (D31/D33/D36–D38) Validation-Queue **inline manual AI override** (1–5 →
`consultant-approved`, keyed by `task_id`, resolves the whole task; local desire feeds only the
landscape, never the AI band; queue lists only actionable MATCHED rows). (D34–D35) **scalability fixes**
— batched HAS inference (`INFER_BATCH=12`) + raised token budgets so large CSVs aren't truncated to
H0/L0. (D39–D42) Mapper UX — optimistic queue removal + "Show reviewed" audit view, a Refresh button,
a **"Reviewed only" filter** that drives the analysis, the Landscape plots capability-scored tasks even
without desire, an explicit AI-Opportunity-Index formula, and a **role-based Roll-up** (impacted roles
+ cumulative org implications). All additive; PAX baseline still **LOCKED (D9): 64 / 34 / 53.1% /
6,620,000 / 6.** **Gate GREEN: 140 backend tests + clean frontend build, zero regressions.**

**Full-build verification + alignment pass (2026-06-30):** ran the complete regression gate from a
clean environment (fresh `.venv` + `npm install`) — **140/140 backend tests pass, frontend builds with
zero TypeScript errors.** PAX baseline parity re-confirmed (64 / 34 / 53.1% / $6,620,000 / 6 layers);
app boots with lifespan + the D13 auth gate active (401 without token). **Backend↔frontend API
alignment audited:** every `services/api.ts` call maps to a real backend route with matching method and
response shape (`{count,items}`, `{steps}`, `{deliverables}`, `ProcessInfo[]`, etc.); frontend `types`
mirror the schemas. Backend routes intentionally **not** surfaced in the UI (no misalignment, all known
/ optional): `GET /deliverables/types`, `GET /validation/stats`, `GET /transition/register`,
`GET /engagements/{id}`, `DELETE /engagements/{id}/real-names` (UI exposes full purge only), and
`GET /audit` (audit UI is the documented optional follow-up). No code changes this session — pure
verification + this summary reconciliation.

**Queue reachability fix + org-hierarchy roll-up (2026-06-30 — D43):** two reported issues fixed.
**(1)** Tasks reviewed/rated in the Validation Queue still showed **"Unreviewed"** on the Workflow
Mapper board (even after Refresh). Persistence was fine — root cause was **queue reachability**: the
frontend defaulted `max confidence = 0.7` as a HARD filter, so model-inferred AI scores with confidence
≥ 0.7 (still export-blocked, still board-flagged "unreviewed") never appeared in the queue and could
never be approved. Fix (frontend-only): confidence is now an **optional priority filter** (blank = show
every item needing review) + a **Select-all** header checkbox for one-pass Approve-all; helper text
clarified. Backend already accepted `max_confidence=None`. **(2)** The Workflow Mapper **Roll-up** now
mirrors the uploaded **org chart**: new additive `GET /api/v1/task-intel/org-rollup` (+
`task_intelligence_service.org_rollup`) returns one node per position with own + **cumulative** H-band
counts rolled UP the reporting line (`manager_key`→`employee_key`, cycle-guarded, anonymization-aware) to
the department heads; the view was rewritten from a flat role list into a **collapsible org-chart tree**
(reporting lines, layers, per-node rolled-up index + H-mix + reports + reviewed%), org-wide stat cards
and index. No existing route/schema/migration changed. Verified end-to-end on Eric's real 25-row CSV (old
cap hid 7/19 tasks; post Approve-all the board shows 0 stuck-unreviewed; tree renders CCO → Global Heads
→ teams). **Gate GREEN: 144 backend tests + clean frontend build, zero regressions.**

**ThinkingBlock 500 fix + Claude Sonnet 5 + model-settings coherence (2026-07-06 — D44):** live
`POST /task-intel/extract` 500'd with `AttributeError: 'ThinkingBlock' object has no attribute 'text'`
— Claude 5-family models return thinking blocks BEFORE the text block, and `claude_service` read
`response.content[0].text`. Fixed: `_response_text()` walks content and joins `type=="text"` blocks
(thinking skipped; informative RuntimeError with `stop_reason` when no text; typeless duck-typed
blocks tolerated). **Extraction now defaults to `claude-sonnet-5`** (latest Sonnet tier; `MODEL_SYNTH`
stays `claude-opus-4-8`); token budgets raised for the Sonnet 5 tokenizer + adaptive-thinking spend
(extract 16000 / benchmark 8192 / infer 6144 / default 4096). Coherence fix: the pipeline now honours
the **Settings-managed models** via `settings_service.model_extract()/model_synth()` (UI → env
fallback) — previously the UI model fields only affected Test-LLM. Skills `resilient-build` (mapped
above) + `web-design-dataviz` installed to `~/.claude/skills/`. 5 new regression tests (written first,
confirmed failing) + an E2E repro through the real route. **Gate GREEN: 149 backend tests + clean
frontend build, zero regressions.**

**GREEN/RED zone coherence + UI clarification (2026-07-06 — D45):** the Workflow Mapper showed the
same H-band in two colours (an H3 task tagged GREEN_LIGHT beside an H3 tagged RED). Root cause: three
scoring paths, only two coherent — `derive_zone(cap, has)` (GREEN only for AI-amenable H1–H2 + high
capability) is used by the WORKBank-overlay and manual-override paths, but the **inference** path stored
the model's OWN `zone` label (the HAS-rubric prompt asks the model to assign zone SEPARATELY from
`has_level`, so it returned H3/H4 + GREEN). Fix: `infer_unmatched_potential` now derives the zone via
`derive_zone(cap, has_level)` (ROBOTICS_GSE_LEVER still honoured for physical tasks). All three paths +
the Validation-Queue label + the board now agree, and GREEN ⇔ AI-amenable H1–H2. Frontend
(WorkflowMapper only): `ZONE_META` gives each zone a plain-language label + one-line meaning + colour,
wired into the task-card badge (tooltip), the inspector Zone box, and a new go/no-go legend. Regression
test (`test_inferred_zone_is_derived_from_has_not_model_label`) + E2E: the screenshot's H3 "Develop
social media content strategy" now reads RED_LIGHT in BOTH the queue and the board. No
schema/route/API change. **Gate GREEN: 150 backend tests + clean frontend build, zero regressions.**

**Roll-up own-vs-team coherence + per-role linked-task detail (2026-07-06 — D46):** the Workflow-Mapper
Roll-up node showed one "N tasks" number = `rollup_tasks` (self + every report), so a head's count read
as tasks they personally own ("CCO has 49 tasks?") and a role's actual tasks weren't visible. Fix
(additive): `org_rollup` now returns per node a `tasks[]` of that role's OWN tasks — each with
`human_agency_level`, `zone`, `review_state`, and `mapped[]` (its `process → step` placement via
TaskLink→ProcessStep→Process; `[]`=unmapped), reusing the same TaskAIScore + mapping Flow/Landscape use.
Frontend (Roll-up only): each row now shows **own** (self_tasks) vs **team** (rollup_tasks · reviewed%)
distinctly (INDEX + bar stay the rolled-up view); **clicking a role expands its own tasks** — H-band
chip, zone dot, text, and `Process · seq. Step` (or "Unmapped"). Alignment verified on Eric's real CSV:
CCO own=1 / team=19 (=org total) / reports 2-24; Head Global Marketing own=1 < team=14; a role's own-task
band/zone/placement matches the Flow board. 2 new/extended tests. No route/schema/migration change.
**Gate GREEN: 151 backend tests + clean frontend build, zero regressions.**

**External research calibration + deploy README (2026-07-14 — D47):** web-harvester (new skill,
installed) calibration pass against primary sources. **Fixed a reversed-quadrant calibration bug** in
the Landscape: per WORKBank (arXiv:2506.06576) Green Light = high capability + HIGH desire (automate)
and Red Light = high capability + LOW desire (workers resist); our labels had these swapped. Quadrants
now use the paper's four zone names + tooltips. HAS rubric text, the HAS-inference prompt, and the
frontend chip names tightened to the paper's exact level definitions; the Workflow Mapper header now
shows BOTH "automation (H1–H2)" and "augmentation (H3–H4)" counts with an explanatory legend (H3 the
most worker-desired level in ~45% of occupations; Anthropic Economic Index 2026 ≈52/45
augmentation/automation). The per-task go/no-go zone stays capability × H-band (D45 — settled),
distinct from the paper's desire-based zones; documented in README §1b. README also gained the
methodology-anchors section and an upgraded §4 deploy guide (pre-flight checklist + "Verify it worked"
checklist) for the non-technical owner. **Gate GREEN: 151 backend tests + clean frontend build, zero
regressions.**

---

## RESILIENT-BUILD SKILL — FILE MAPPING (do NOT create parallel files)

The `resilient-build` skill governs this project, but its generic state files are **mapped onto this
repo's existing files** — never create the skill's default filenames alongside them:

| resilient-build concept        | THIS repo's file (use this)                                   |
|--------------------------------|---------------------------------------------------------------|
| `PROJECT_STATE.md` (resume)    | `.checkpoints/LATEST.md` (+ the one-paragraph summary above)   |
| `DECISIONS.md`                 | `.checkpoints/DECISIONS.md`                                    |
| build journal                  | `PROGRESS.md` (append-only)                                    |
| `GUIDE.md` (owner's manual)    | `README.md` (B7 run/deploy/usage guide)                       |
| `API_CONTRACT.md`              | `backend/app/api/schemas.py` ⇄ `frontend/src/types/index.ts` + `frontend/src/services/api.ts` (enforced by the test suite) |
| `run_checks.sh`                | `scripts/gate.sh` (a.k.a. `make gate`)                         |
| baseline / golden snapshots    | `.checkpoints/BASELINE.md` + `backend/tests/baseline/`        |

The skill's session loop, scope-lock, anti-hallucination, and "full gate after every change" rules are
the SAME discipline already written into Part A below — follow Part A; the skill reinforces it.

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

> Part B (requirement specification), B0–B7, lives in `BUILD_SPEC_ADVISORY_WORKBENCH.md`. Read it
> for what to build each phase. This file governs *how* to build.
