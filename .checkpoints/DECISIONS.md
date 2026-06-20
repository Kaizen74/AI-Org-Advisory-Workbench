# DECISIONS LOG (append-only)

Each entry: date, decision, rationale. Never reverse a settled decision without adding a new entry
that supersedes the old one and explains why.

---

## 2026-06-11 — D1: Carried-over architecture decision — logical overlay join (NOT a hard FK)

**Source:** `docs/WORKFORCE_INTELLIGENCE_ARCHITECTURE.md` §2–§3; Build Spec B0.
**Decision:** The AI overlay (`task_ai_overlay`) is joined to tasks **logically by
`onet_task_code`**, never via a hard foreign key. **Rationale:** WORKBank is keyed to O*NET, so the
overlay must stay independently replaceable when real WORKBank pulls arrive — a hard FK would
couple the overlay to task rows and block clean replacement. **Carried over** from the legacy WI
architecture and applies unchanged to this greenfield build.

## 2026-06-11 — D2: Carried-over architecture decision — three-layer separation

**Source:** `docs/WORKFORCE_INTELLIGENCE_ARCHITECTURE.md` §1; Build Spec B0.
**Decision:** Maintain three separated layers: (1) **Reference layer** — the pluggable taxonomies
(SFw/O*NET/WORKBank), engagement-independent, seeded once; (2) **Pipeline layer** — per-engagement
results that cascade under an engagement/dataset (extract → benchmark → AI overlay → rollup);
(3) **Presentation layer** — reads only persisted results, never recomputes from raw inputs.
**Rationale:** Keeps reference data reusable across engagements, keeps engagement data cleanly
purgeable (FK cascade), and keeps the UI a pure read of persisted, provenance-tagged results.

## 2026-06-11 — D3: SUPERSEDED architecture decision — the "single cross-boundary FK" rule

**Source:** `docs/WORKFORCE_INTELLIGENCE_ARCHITECTURE.md` §1 ("the ONLY cross-boundary FK":
`workforce_intelligence_result.analysis_id → org_analyses.id`); Build Spec B0.
**Decision:** The legacy rule that the WI module attaches to the existing app via exactly **one**
cross-boundary FK (into `org_analyses`) is **SUPERSEDED** and does NOT apply here. **Rationale:**
That rule existed because the legacy app was a *brownfield* add-on walled off from an existing
diagnostic schema. This is a **greenfield** schema where **tasks are first-class rows**
(`tasks`, `task_benchmarks`, `task_ai_scores`) hung off `positions`/`datasets`/`engagements` with
normal FK cascade. There is no single results blob and no walled-off boundary to protect.

## 2026-06-11 — D4: Development branch (harness requirement) vs. spec's "work on main"

**Source:** Session harness "Git Development Branch Requirements"; Build Spec A2.
**Decision:** Develop Phase 0 on branch **`claude/compassionate-knuth-wx5bjq`** (the harness-
designated branch) rather than directly on `main`. **Rationale:** The execution harness explicitly
mandates this branch and forbids pushing elsewhere without permission; this overrides the spec's
"work on `main` until P1" convention for the build-memory commits. The `origin` remote is already
connected (the working dir is a clone of the GitHub repo). Eric can merge this branch into `main`
when Phase 0 is approved.

## 2026-06-11 — D5: `legacy/` folder missing at Phase 0 — port BLOCKED, will not reinvent

**Source:** Build Spec B0 ("If `legacy/` ... is missing at Phase 0, STOP and record in `LATEST.md`
exactly what is missing — do not reinvent these assets.").
**Decision:** The `legacy/` v1 app folder is **absent** from the repo. The two legacy-derived P0
assets — (a) the `_json_utils.py` port from `work_activities_service.py`, and (b) the PAX CSV +
expected-metrics test fixture (`backend/tests/fixtures/`) — are **left un-ported** and Phase 0 is
**held open** for them. **Rationale:** The spec forbids reinventing these proven assets; fabricating
them risks diverging from v1 behaviour and would break the P1 PAX parity baseline
(total_employees=64, total_cost=5770000, etc.). All other Phase 0 work (which does not depend on
`legacy/`) is completed so the session is not wasted. Awaiting Eric's delivery of `legacy/`.

## 2026-06-11 — D6: `legacy/` delivered as a zip on `main`; tracked as an unpacked folder on the branch

**Source:** Eric uploaded `legacy v1 app.zip` to the `main` branch (resolving the D5 blocker).
**Decision:** Extract the zip and **commit the unpacked `legacy/` folder** (61 files, no secrets/db/
node_modules) on the working branch `claude/compassionate-knuth-wx5bjq`, matching the Build Spec B0
repo layout (which lists `legacy/` as a tracked reference folder). **Rationale:** Committing the
unpacked folder (not the zip) gives a fresh-clone session the reference material directly — the
off-machine memory-resilience goal — and lets phase instructions PORT files path-by-path. The zip
remains on `main` as Eric's upload artifact; he can delete it after this branch merges (noted in
LATEST.md). `legacy/` is reference-only and is never imported as a package (B0).

## 2026-06-14 — D11: LLM provider + API key configurable via UI; local-LLM fallback allowed

**Source:** Eric's pre-P7 request ("review where Claude API is captured/stored and ensure this is
done through the UI ... allow connect to local LLM on my laptop ... when online frontier AI models
are disrupted").
**Decision:** Introduce an `app_settings` key/value table + `settings_service` (DB-backed with an
in-memory cache) and a `/api/v1/settings` UI. The Anthropic API key is entered/stored **through the
UI** (DB, gitignored; masked on read) with env as fallback. A `llm_provider` setting switches between
`anthropic` and a **local OpenAI-compatible endpoint** (e.g. Ollama/LM Studio) configured by
`local_base_url` + `local_model`. `claude_service.complete(...)` keeps its public signature/return
shape but routes by provider (local calls go via `httpx` to `{base_url}/chat/completions` — no heavy
ML deps added, A4 ban respected). **This SUPERSEDES the A4 "Claude API only for inference" guardrail**
at the owner's explicit instruction, to keep the tool usable during frontier-model outages.
Regression tests prove the prior Anthropic path is preserved.

## 2026-06-14 — D13: Private access control (email + passcode allowlist), app not public

**Source:** Eric's pre-deploy instruction ("this app is not deployed in a public space ... provide
an identifier (email) and passcode for select ones to access ... cannot show the default brand look
and feel to the public").
**Decision:** Add **app-level authentication**: a neutral (un-branded) login screen; a backend
allowlist of `access_users` (email + salted-PBKDF2 passcode hash, `is_owner` flag); `POST
/api/v1/auth/login` returns an HMAC-signed token (stdlib only — no new deps) with a TTL; **every
`/api/v1/*` route except `auth` is protected** (`/health` stays open for platform health checks).
Owners manage the allowlist via `/api/v1/access` (owner-only) and a Settings UI. The allowlist is
bootstrapped from an `ACCESS_USERS` env var on first run; `AUTH_SECRET` signs tokens. The app is
still hosted on Vercel/Railway but **content + SATS branding sit entirely behind login** — the public
sees only a generic sign-in. Tests override the auth dependency so existing suites are unaffected; new
tests cover the login + gate. This refines the deploy plan (README §4) — it does not change any
feature behaviour.

## 2026-06-14 — D12: Brand template configurable (logo + palette) via Settings

**Source:** Eric's pre-P7 request ("allow brand logo and color palette to be changed/swapped which
in turn adjusts the brand deck template accordingly").
**Decision:** Brand name, palette (ink/accent/muted/rule/ground) and a logo are stored via
`settings_service` (logo file in gitignored `backend/uploads/brand/`). `deliverable_theme` gains
`theme_from_settings()`; the deliverable generators accept `template="brand"` to render with the
stored palette + logo on the title slide. The modern-minimalist theme (D10) remains the default and
fallback. Extends D10 (does not reverse it).

## 2026-06-14 — D10: Deliverable template — modern-minimalist default; SATS brand deferred

**Source:** Eric's P6 instruction ("adopt a modern minimalistic style deck template ... refer to my
project 'business ideas' for inspiration ... for now").
**Decision:** Ship a **modern-minimalist** template as the default (`deliverable_theme.py`):
near-black ink `#1F2933`, muted-teal accent `#2F6F6A`, light rule `#E5E7EB`, white ground, generous
whitespace, light-weight large titles, thin divider rules. The Build Spec B4 said "SATS-brand
template first, generic second"; this is **superseded for now** by Eric's explicit request for a
minimalist style. **Rationale:** Eric's 'business ideas' project is not reachable from this
repo-scoped session, so its exact tokens can't be pulled; the minimalist palette is a safe, on-brief
default. The generator takes a `template` arg and the theme is centralized, so a SATS-branded theme
(logo/palette/fonts) drops in later without touching generator logic. **Open question logged** for
Eric to supply brand assets or 'business ideas' tokens when convenient.

## 2026-06-11 — D9: RESOLVED D8 — the provided PAX CSV is the source of truth

**Source:** Eric's decision in response to the D8 escalation ("Use the provided CSV as truth").
**Decision:** The P1 PAX parity target is reset to the values the provided `org_structure_PAX.csv`
actually produces under the faithful port: **total_employees=64, total_managers=34,
manager_ratio_pct=53.1, total_cost=6,620,000, organizational_layers=6**. These — not the spec's
illustrative 16 / 25.0 / 5,770,000 — are now the locked golden baseline (`expected_pax_metrics.json`
+ `backend/tests/baseline/`). **Rationale:** Eric confirmed the zip's CSV is the canonical fixture;
"parity with v1" is preserved in spirit because the port reproduces the legacy v1 code's output on
this file byte-for-byte. The spec's numbers referred to an earlier PAX file and are superseded for
baseline purposes. P1.5 is unparked.

## 2026-06-11 — D8: PAX fixture CSV conflicts with the Build Spec's P1 parity numbers (ESCALATED)

**Source:** Running the faithful CSV-parser + metrics port (and the legacy v1 code itself) on the
`org_structure_PAX.csv` from Eric's `legacy v1 app.zip`.
**Observation:** The provided CSV yields **64 employees, 34 managers (53.1%), $6,620,000 total cost,
6 layers**. The Build Spec A3 Rule 2 (and PRD) require P1 parity of **64 / 16 / 25.0 / 5,770,000 /
6**. Only `total_employees` (64) and `organizational_layers` (6) agree. `total_cost` is a raw salary
sum, and this CSV's salaries sum to 6,620,000 — so no definition of "manager" can reconcile it; the
zip's CSV is a **different/newer file** than the one the spec parity (and the legacy app's own
`test_metrics.py`, which also expects 5,770,000) was written against. The port is **faithful** — it
reproduces the legacy code's numbers on this CSV exactly.
**Decision (conservative, pending Eric):** Do NOT fabricate metrics to hit the spec numbers and do
NOT lock a parity baseline yet. The committed parser tests assert (a) the undisputed values
(64 / 6) and (b) the *actual* fixture output (34 / 6,620,000 / 53.1%) clearly flagged as pending.
P1.5 (metrics parity baseline + BASELINE.md lock) is **parked** until Eric chooses: (A) treat the
provided CSV as source of truth and reset the parity target to the actual numbers, or (B) upload the
correct PAX CSV that produces 16 / 25.0 / 5,770,000. Recorded as an open question in LATEST.md.

## 2026-06-11 — D7: `_json_utils` port keeps the legacy raw-JSON contract (closing-brace required)

**Source:** Port of `work_activities_service._parse_response` into `app/services/_json_utils.py`.
**Decision:** Preserve the legacy behaviour exactly: `parse_ai_json` only attempts truncated-JSON
repair when the extracted span contains a closing `}`; a string with no `}` short-circuits to the
`{"error": "Could not parse response"}` envelope rather than being repaired. **Rationale:** Faithful
ports must not silently "improve" behaviour (Part A additive-only / no-silent-change). Tests in
`test_json_utils.py` lock this contract so a future phase cannot regress it. (A test I first wrote
asserted the wrong expectation; the test was corrected, not the ported code.)

## 2026-06-15 — D14: Salary column matched by header variant, not exact "Salary"

**Source:** Eric's bug report — uploaded "Global Mkrting Co" CSV showed **TOTAL COST $0** despite a
populated salary column.
**Root cause:** `OrgCSVParser._clean_data` matched the salary column by the exact string `"Salary"`.
The real export's header was **`"Salary ($)"`**, so no column matched and every `salary` defaulted
to 0, propagating to `cost_analysis.total_cost = 0`.
**Decision:** Resolve the salary column tolerantly via `_find_salary_column`: exact `"Salary"` wins;
otherwise the first column whose normalized (lowercased, stripped) name **contains "salary"** (covers
`Salary ($)`, `Salary (USD)`, `Annual Salary`, `Base Salary`, `SALARY`). Existing `$`/`,` cleaning and
`NA→0` coercion are unchanged. **Additive/backward-compatible:** the PAX fixture uses exact `"Salary"`
and its LOCKED baseline (total_cost 6,620,000) is unchanged. **Regression tests:**
`test_csv_parser.py::test_salary_column_header_variants_are_recognized` and
`::test_currency_formatted_salary_values_are_parsed`.

## 2026-06-16 — D15: Authenticated file downloads via blob fetch, not browser-direct URLs

**Source:** Eric's bug report — "Download instrument (.xlsx)" returned `{"detail":"Not authenticated"}`.
**Root cause:** D13 gated every `/api/v1/*` feature router with `Depends(require_auth)`, which reads
the `Authorization: Bearer` header. Four spots opened file endpoints by **browser-direct navigation**
(`<a href>` / `<img src>`) — the desire-pulse instrument, the transition register, deliverable
downloads, and the Settings brand-logo preview — and the browser cannot attach the token header to
those, so every one returned 401.
**Decision:** Keep the backend auth contract **header-only** (no token-in-URL query param, which would
leak tokens into browser history / access logs / Referer — at odds with the app's privacy/audit
posture). Fix on the frontend: added `authedBlob()` + `downloadBlob()` in `services/api.ts` that fetch
the file **with the Bearer header**, then save via a temporary object URL. Replaced the four URL-builder
methods (`pulseInstrumentUrl`/`transitionRegisterUrl`/`deliverableDownloadUrl`/`brandLogoUrl`) with
`downloadPulseInstrument` / `downloadTransitionRegister` / `downloadDeliverable(id, filename)` /
`brandLogoObjectUrl()`; call sites became buttons (logo renders from a fetched object URL, revoked on
change). **Additive/backward-compatible:** no backend change, no route/signature/schema change.
**Verification:** no frontend test runner exists, so proven via (a) clean `npm run build`, and (b) a
TestClient check on the gated endpoint — 401 without the header, auth-passes with a valid token. Full
gate green (114 backend tests + build).

## 2026-06-16 — D16: Validation-queue legibility + Workflow Mapper step UX/connection

**Source:** Eric's report — (1) the validation queue "feels like a lot of duplicates" and "SkillsFuture
(SFw) benchmark data seems missing"; (2) Workflow Mapper steps "don't register" on Add; (3) the AI
opportunity matrix seems "disconnected from the selected tasks/step/process".
**Findings:**
1. Not real duplicates — distinct tasks rendered identical labels because the queue showed only a
   generic label (`{status} → O*NET {code}` / `{level} · zone {zone}`) with no task text, AND the
   benchmark label hardcoded "O*NET" even though SFw is the default seeded source (so SFw looked
   absent). SFw IS seeded (`SFW_AIR_TRANSPORT`, default). For a marketing dataset nothing matches the
   illustrative air-transport seed, so all benchmarks are `EXTRA` (conf 0) and all scores are L0
   robotics levers — hence the wall of identical-looking rows.
2. Backend step creation/linking is correct (proven by tests), but the frontend never listed steps:
   it kept only the latest `stepId` in state with no visible list/counts, so adding a step gave no
   feedback and you couldn't pick which step to map to.
3. The matrix backend correctly aggregates linked tasks, but the UI showed only bare L0–L3 counts with
   no tie to tasks; with the broken step UX, fewer tasks linked than intended, so counts looked wrong.
**Decisions (additive):**
- Backend: `validation_service.get_queue` now attaches `task_text` to benchmark/ai_score items and
  builds the benchmark label from the ACTUAL `taxonomy_source_code` (SFw/O*NET), not a constant.
  New `GET /api/v1/workflows/{process_id}/steps` (+ `workflow_service.list_steps`) returns each step
  with its `linked_tasks` count; `POST .../steps` now also returns `linked_tasks: 0`.
- Frontend: ValidationQueue shows task text as the primary ITEM line (label demoted to subtext).
  WorkflowMapper renders the steps list (selectable, with counts), gives add/link confirmations, and
  the matrix card now shows per-level **evidencing task text** + a warning when nothing is linked.
**Verification:** 3 new backend tests (queue task_text+source; steps list/counts; matrix sum == linked
count) + an e2e reproducing the marketing scenario. Full gate green (117 backend tests + clean build).
No existing route/signature changed destructively; the benchmark-label test still passes (onet code
retained in the label when matched).

## 2026-06-16 — D17: Refocus — park the scenario simulator; make Human Agency Scale (H0–H5) the headline

**Source:** Eric's product reflection — the app was "trying to do too much by squeezing in the scenario
planner (role simulation + scenario comparison)". He wants the focus on **breaking roles into tasks and
identifying AI potential (H0–H5) with benchmark insights.** Decisions chosen via AskUserQuestion:
(1) headline scale = **surface the WORKBank Human Agency Scale**; (2) Scenario Studio + Transition
Planner = **hide behind a flag (reversible)**; (3) Diagnostics + Workflow Mapper = **keep as supporting**.
**Decisions:**
- **Focus (reversible):** frontend `App.tsx` gains `SHOW_SIMULATION = false`; the Scenario Studio and
  Transition Planner tabs are removed from the nav while their pages, routes, services, tables and all
  tests are retained untouched — re-enabling is a one-line flip. No backend/route/schema change, so the
  scenario/transition suites stay green (additive-only honoured).
- **Headline = HAS (H0–H5):** added `human_agency_band(has_level)` and the `HUMAN_AGENCY_SCALE` rubric
  to `task_intelligence_service`. H0 = no software-agent overlay (physical/robotics lever); H1–H5 = the
  WORKBank HAS. **Direction (from the seed): lower H = more AI-amenable** (GREEN_LIGHT/automatable seeds
  are H2; RED_LIGHT is H4). The rollup bucket now carries an `agency` H0–H5 breakdown and the payload
  ships the rubric; the validation queue's ai_score rows lead with the H band; the Task Intelligence
  page makes the H0–H5 chart + rubric the headline, demoting L0–L3 to a supporting view.
- **L0–L3 retained internally** (rollup `levels`, workflow matrix, scenario code) — additive, no
  destructive change; the HAS band is derived from the already-stored, independent `has_level`
  (capability/has_level still never collapsed, per the WORKBank guardrail).
**Open / deferred (need Eric):** (a) confirm the H0 definition and the H1→H5 direction above match his
intent (the HAS level *descriptions* remain ILLUSTRATIVE — verify vs the WORKBank source before client
use); (b) optionally re-band the Workflow Mapper "AI opportunity matrix" from L0–L3 to H0–H5 for
consistency; (c) optionally slim the Deliverables to the diagnostic + AI-potential story (drop the
scenario-comparison deck). **Verification:** +1 unit test (band mapping) + extended rollup/queue asserts;
full gate green (118 backend tests + clean frontend build).

## 2026-06-16 — D18: Workflow Mapper UX — run progress, mapping-coverage output, authored-vs-CSV clarity

**Source:** Eric's review of the Workflow Mapper. (1) "Run" on the AI opportunity matrix gave no visible
progress. (2) No visible output of what was mapped (linked / left / missing). (3) Asked whether
processes/steps are new labels vs. linking what exists in the CSV.
**Clarification recorded (3):** Processes and steps are **authored in the app** (the value-stream /
workflow structure is NOT in the uploaded org CSV — a CSV carries roles→activities, not processes). The
CSV-derived, extracted **tasks** are then **linked** onto those authored steps via `TaskLink`. So it is a
hybrid by design (M4 "follow the work"): authored process/step skeleton + linked existing tasks. A short
explanatory note now states this in the Processes card.
**Changes (additive):**
- `workflow_service.list_steps` now returns `linked_task_ids` per step (kept `linked_tasks` count) — drives
  the coverage view. Additive to the dict; existing count test still passes.
- Frontend `StepInfo` gains `linked_task_ids`; WorkflowMapper: (1) `running` state → "Running…" button +
  spinner in the matrix card; (2) a full-width **Mapping coverage** card (no API key needed): progress bar
  (linked / total extracted tasks), stat tiles (steps / linked / unlinked / empty steps), and lists of
  "Unlinked tasks — what's left" and "Steps with no tasks — what's missing".
**Verification:** extended `test_steps_listed...` to assert `linked_task_ids`; gate green (118 backend
tests + clean frontend build, zero regressions). The L0–L3 matrix is unchanged (re-banding to H0–H5 per
D17 remains an open follow-up).

## 2026-06-16 — D19: Re-band the Workflow Mapper AI-opportunity matrix from L0–L3 to H0–H5

**Source:** Eric — after D17 made the WORKBank Human Agency Scale the headline AI-potential metric, the
Workflow Mapper matrix still showed L0–L3; he asked to re-band it to H0–H5 for consistency.
**Changes (additive):**
- `workflow_service._process_level_counts` now also computes an H0–H5 banding from each linked task's
  `has_level` (`human_agency_band`): per-step `agency_counts`, process-wide `agency_matrix`, and
  `agency_evidencing` (task text per band). L0–L3 (`matrix`, `level_counts`, `evidencing_tasks`) is
  **retained internally** (additive-only). The matrix payload also ships the `human_agency_scale` rubric.
- `_ai_priority` prompt now includes the HAS distribution (mock returns canned JSON regardless).
- Frontend `OpportunityMatrix` type + WorkflowMapper switched the headline grid/evidencing to H0–H5
  (6-tile grid, rubric tooltip, "lower H = more AI-amenable; H0 = robotics/GSE lever" caption).
**Verification:** extended `test_workflow_mapping_and_opportunity_matrix` (agency_matrix band-set, sum ==
linked count, rubric keys, step agency_counts). Live smoke: 2×L3 tasks band as H2; agency sum == linked.
The H0≥1 assertion was dropped as fixture-specific (this fixture scores every task) — H0 semantics stay
covered by the Task Intelligence rollup test. Gate green (118 backend tests + clean frontend build,
zero regressions); backend↔frontend keys aligned, tsc clean.

## 2026-06-16 — D20: Visual Workflow & Task-analysis Mapper (board) integrated, refined to H0–H5

**Source:** Eric supplied an integration package (drag-to-remap board: Flow / Landscape / Roll-up,
hover role-trace, undo, inspector) and asked to replicate + refine it. Via AskUserQuestion he chose to
**refine the headline to the Human Agency Scale (H0–H5)** (consistent with D17–D19), keeping L0–L3 as a
secondary detail.
**Changes (additive — no migration; reuses Process/ProcessStep/Task/TaskAIScore/TaskLink/Position):**
- Backend `workflow_service`: `Position` import; new `_board_task_payload`, `board`, `_process_step_ids`,
  `move_task`, `unmap_task`. The board payload exposes real persisted fields per task (role=job_title,
  department, zone, capability/desire, confidence, review_state, rationale, ai_level) **plus the headline
  `human_agency_level` (H0–H5) + raw `has_level`**, and ships the `human_agency_scale` rubric.
- Backend `workflows.py`: `MoveTaskBody`/`UnmapTaskBody` + `GET /{id}/board` (no key), `POST /{id}/move-task`,
  `POST /{id}/unmap-task` (move validates the target step belongs to the process → 404 otherwise). All
  inherit the D13 auth gate (router included with `require_auth`).
- Frontend: `BoardTask`/`BoardStep`/`WorkflowBoard` types (+`AgencyBand`); `api.workflowBoard/moveTask/
  unmapTask`; WorkflowMapper.tsx replaced with the visual board, **refined so cards/filters/legend/
  Landscape dots/Roll-up mix are encoded by H0–H5** (lower H = more AI-amenable; H0 = robotics/GSE off
  the agent scale). The AI opportunity index is a HAS-weighted potential; "AI-amenable" = H1–H2; L0–L3
  shown as a secondary chip in the task inspector. The board's unmapped tray + per-step counts subsume
  the D18 "mapping coverage" card (D18's `linked_task_ids` on `list_steps` is retained + still tested).
- Mapping now happens via drag → `move-task` (mapping from the unmapped tray adds a link; moving removes
  the prior in-process link first). The legacy `map-tasks` endpoint/`api.mapTasks` remain (tested, unused
  by the page).
**Verification:** new `test_workflow_board.py` (3 tests, refined to assert `human_agency_level` +
rubric); live board smoke (role=job_title, H2/L3, drag persists). Gate green — **121 backend tests +
clean frontend build**, tsc clean, backend↔frontend keys aligned, zero regressions.

## 2026-06-16 — D21: Drop the scenario deck; focus Deliverables; centralize SHOW_SIMULATION

**Source:** Eric — "drop the scenario deck and keep this app clean towards basic org-metric compute,
Workflow Mapper, and Task Intelligence with external benchmarking + editing features."
**Decision (consistent with D17 — park, don't delete):**
- The two simulation deliverables — `PPTX_SCENARIOS` (scenario comparison deck) and `XLSX_TRANSITION`
  (transition register) — are now gated behind `SHOW_SIMULATION` in the frontend `Deliverables` page
  (the buttons + scenario selector + the `listScenarios` fetch). With the flag off they are not offered.
- The flag was **centralized** into `frontend/src/config.ts` (`export const SHOW_SIMULATION = false`) and
  imported by both `App.tsx` (nav tabs) and `Deliverables.tsx` — one switch restores all simulation
  surfaces (Scenario Studio, Transition Planner, scenario/transition decks) at once.
- **Backend left intact (reversible):** the `_gen_pptx_scenarios` / `_gen_xlsx_transition` generators,
  `DELIVERABLE_TYPES`, and the `/deliverables` routes are unchanged — capability retained, just not
  surfaced. No backend test churn.
- Kept Deliverables: Diagnostic deck (org metrics), AI roadmap (task-level AI potential), TOM narrative,
  Metrics pack — aligned to the focused surface (Diagnostics + Workflow Mapper + Task Intelligence
  benchmarking/editing).
**Verification:** tsc clean; gate green (121 backend tests + clean frontend build, zero regressions).

## 2026-06-16 — D22: 'Finalized workflow' deliverable (PPTX_WORKFLOW)

**Source:** Eric — be able to print out the finalized workflow as a deliverable type.
**Decision (additive):** new `PPTX_WORKFLOW` deliverable. `_gen_pptx_workflow(engagement_id, dataset_id)`
iterates the engagement's processes and, per process, uses `workflow_service.board(process, dataset)`
to emit a section slide of the **finalized mapping** — each step with its mapped tasks shown as
`text [role · H-band]`, the per-step Human-Agency (H0–H5) mix, and a `Mapped m/n · u unmapped` line —
then a provenance/caveats slide (export-block + disclosure unchanged). Mapped tasks only (unmapped count
disclosed). Registered in `_EXT` + `_GENERATORS`; surfaced in the frontend Deliverables page as
"Finalized workflow (.pptx)" (uses the active dataset; engagement_id always passed).
**Alignment:** backend `DELIVERABLE_TYPES` now includes PPTX_WORKFLOW and `/deliverables/types` returns
it; frontend button added. No schema/route change.
**Verification:** updated `test_generate_all_types_and_provenance` (now 7 types) + new
`test_workflow_deliverable_reflects_mapping` (maps a task → valid PK file → type offered). Live content
smoke confirmed the deck shows the process/step/H-band/mapped line + provenance. Gate green — **122
backend tests + clean frontend build**, tsc clean, zero regressions.

## 2026-06-16 — D23: Workflow reset, engagement deletes, and honest benchmark/zone classification

**Source:** Eric's review — (1) Undo/Reset board looked inactive; (2) no delete for client/engagement/CSV;
(3) the validation queue mislabeled Global-Marketing knowledge work as "ROBOTICS_GSE_LEVER".
**Fixes:**
1. **Reset board (active + meaningful):** new `workflow_service.reset_board` + `POST /workflows/{id}/
   reset-board` (unmap ALL tasks for a process → 404 if missing, idempotent). Frontend "Reset board" now
   clears the board (confirm dialog) and is enabled whenever `mapped_count>0` OR there are session moves;
   Undo stays the session-scoped per-move revert (tooltip clarified). Resolves the "inactive" perception.
2. **Deletes:** `engagement_service` gained `delete_dataset`, `delete_client`, and a shared
   `_delete_dataset_chain` / `_purge_engagement_data` doing thorough ordered child→parent deletes
   (TaskLink/TaskAIScore/TaskBenchmark/Task → MetricValue/Position → Process/Step → Scenario children →
   DesirePulse/Deliverable/AuditEvent → Dataset). `purge_engagement` now reuses it (no longer leaves
   orphan tasks). Routes: `DELETE /engagements/clients/{id}`, `DELETE /engagements/{id}`,
   `DELETE /engagements/datasets/{id}`. Frontend Engagements page: ✕ delete buttons (client/engagement/
   dataset) with confirms + state cleanup.
3. **Honest classification (the core relevance fix):** `score_ai_opportunity` split the no-overlay branch
   — benchmark-MATCHED-but-no-overlay → `ROBOTICS_GSE_LEVER` (physical lever, unchanged); NO benchmark
   match at all → new `NO_BENCHMARK_MATCH` zone (source model-inferred, conf 0.0, rationale "load a
   relevant benchmark — not a robotics/GSE lever"). Added `unclassified` to the result. So a marketing
   dataset against the air-transport seed now shows 0 robotics levers + N unclassified (was all robotics).
   H0 rubric broadened to cover "physical OR not-yet-benchmarked". Validation queue benchmark rows with no
   match now read "MISSING → no benchmark match (load a relevant taxonomy)" instead of "EXTRA → — —".
**Verification:** +5 tests (reset-board, dataset/engagement/client delete, full-pipeline cascade,
no-match→NO_BENCHMARK_MATCH); live marketing smoke (robotics 0, zone NO_BENCHMARK_MATCH). Gate green —
**125 backend tests + clean frontend build**, tsc clean, backend↔frontend aligned, zero regressions.

## 2026-06-16 — D24: Robust AI benchmarking via Claude grounded in the WORKBank HAS rubric

**Source:** Eric — should benchmarking connect to live external taxonomies (WORKBank / O*NET / ESCO)
rather than the illustrative seed?
**Determination:** No live external API wiring.
- **WORKBank** ("Future of Work with AI Agents", Stanford) is a *static research dataset* (HF/GitHub),
  not a live API. **O*NET / ESCO** have APIs but add API keys, latency, licensing, and offline-test
  breakage; committing their full datasets violates guardrail A4 (~200MB budget; full O*NET/SFw/ESCO
  banned). (No recognised "WolfTech" taxonomy exists — likely O*NET/ESCO/SFw/Lightcast.)
- **Chosen approach:** use **Claude — the app's sanctioned inference engine — grounded in the WORKBank
  Human Agency Scale rubric** (and its O*NET/ESCO/SFw knowledge) to benchmark tasks the curated
  seed/overlay can't match. The curated overlay stays authoritative; inferred scores are tagged
  `model-inferred` + `unreviewed`, so the export-block (M6) keeps them out of client deliverables until
  a consultant approves them. Honors Claude-API-only, no-heavy-deps, no-huge-datasets, and provenance.
**Implementation (additive — existing deterministic scoring unchanged):**
- `task_intelligence_service.infer_unmatched_potential(dataset_id)`: finds `NO_BENCHMARK_MATCH`
  ai_scores, sends their text to Claude with a HAS-rubric prompt (marker `HUMAN AGENCY SCALE
  BENCHMARK`), parses per-task {has_level, capability_score, zone, confidence, rationale}, updates the
  rows (L0-L3 via `derive_ai_level`; source model-inferred; review_state unreviewed; rationale
  annotated "AI-inferred — verify before client use"). Idempotent; no-op if no candidates.
- Endpoint `POST /task-intel/infer-potential` (key required, audited).
- Frontend: `api.inferPotential` + `AIInferResult` type; the Task Intelligence "Run pipeline" now runs
  extract → benchmark → ai-opportunity (curated) → **infer-potential (HAS rubric)** → rollup.
  `AIOpportunityResult` gained `unclassified` (D23) for alignment.
**Verification:** new `test_infer_unmatched_potential_via_rubric` (marketing dataset → all unmatched →
inferred H2/GREEN_LIGHT, still model-inferred/unreviewed, idempotent). Gate green — **126 backend tests
+ clean frontend build**, tsc clean, backend↔frontend aligned, zero regressions.

## 2026-06-16 — D25: WORKBank dataset integration path + fix lingering robotics levers

**Source:** Eric — integrate the WORKBank GitHub DB (SALT-NLP/workbank) instead of separate taxonomy
uploads + over-reliance on Claude inference; and still seeing ROBOTICS_GSE_LEVER on some queue items.
**Findings:** The WORKBank GitHub repo holds only analysis notebooks + O*NET/BLS reference data + the
codebook; the per-task tables (Human Agency Scale, expert capability, worker desire) are on **Hugging
Face** (`SALT-NLP/WORKBank`). **`huggingface.co` is NOT in this environment's egress allowlist** (GitHub
is — clone succeeded), so the real values can't be pulled from the sandbox right now.
**Approach (layered authority):** curated/consultant-approved overlay > **WORKBank overlay** (real,
authoritative) > Claude HAS-rubric inference (last resort). Implemented the integration *mechanism* so
the data drops in cleanly once HF is reachable:
- `scripts/build_workbank_overlay.py`: converts the 3 WORKBank CSVs → a curated overlay JSON in our
  schema (aggregated to O*NET-SOC level; mean capability/desire, modal HAS; zone derived). Fuzzy column
  matching (schema-tolerant), `--limit`/attribution, writes `workbank_overlay.curated.json`.
- `taxonomy_loader`: refactored overlay upsert into `_upsert_overlay`; added an additive hook that loads
  the optional `WORKBANK_OVERLAY_PATH` curated file (source="WORKBank") when present — absent ⇒ seed-only
  (no behaviour change). Did NOT fabricate WORKBank values.
**Robotics fix (B):** `infer_unmatched_potential` now re-evaluates BOTH `NO_BENCHMARK_MATCH` and the
auto-assigned model-inferred `ROBOTICS_GSE_LEVER` rows via the HAS rubric — Claude re-bands misclassified
knowledge work (H1-H5) and keeps genuinely physical tasks as a robotics lever (has_level null). Rationale
is tagged `[WORKBank HAS inference]` for idempotency (confirmed physical levers aren't re-processed).
**To activate real WORKBank data:** add `huggingface.co` to the env egress allowlist (or download the CSVs
locally), run the build script, commit the curated subset. Then far fewer tasks need inference.
**Verification:** +2 tests (robotics correction + curated-overlay load); build script compiles; live
behaviour covered by D24 tests. Gate green — **128 backend tests + clean frontend build**, tsc clean,
backend↔frontend aligned, zero regressions.

## 2026-06-16 — D26: Harden WORKBank ingestion (importable + tested) + benchmark source-mix transparency

**Source:** Eric reconfirmed the HF dataset URL and asked for the best robust-benchmarking approach + a
verifying test. **`huggingface.co` is STILL not in this environment's egress allowlist** (re-checked: 403
"Host not in allowlist") — enabling it is an environment network-egress setting (Claude Code on the web),
not changeable from the sandbox. So the live tables still can't be pulled here; I hardened+verified the
ingestion path so the data drops in cleanly once HF is allowlisted.
**Changes (additive):**
- Extracted the converter into `app/services/workbank_ingest.build_overlay_from_dir` (importable, pure,
  schema-tolerant; aggregates WORKBank tasks to O*NET-SOC level: normalised capability/desire, modal HAS,
  derived zone). `scripts/build_workbank_overlay.py` is now a thin CLI over it. This let me UNIT-TEST the
  D25 converter logic offline against synthetic WORKBank-shaped CSVs (capability normalisation, HAS
  aggregation, zone) — previously unverifiable.
- **Benchmark source-mix transparency:** `rollup` now returns `source_mix`
  {overlay, ai_inferred, robotics, unclassified} via `_benchmark_source(score)`, and the Task Intelligence
  page shows a "Benchmark coverage" card. This makes reliance on Claude inference *visible/measurable*
  (Eric's concern) and signals when loading a WORKBank overlay would help.
- Verified the **layering** end-to-end: a task whose O*NET code is covered by the WORKBank overlay is
  scored from the overlay (source=WORKBank, real has_level) and inference is a no-op — proving the overlay
  reduces inference.
**To go live:** allowlist `huggingface.co` → download the 3 CSVs → `python scripts/build_workbank_overlay.py
--src ./workbank_csv` → commit `workbank_overlay.curated.json` (loader auto-picks it up).
**Verification:** +2 tests (converter aggregation; overlay-bypasses-inference incl. source_mix). Gate green —
**130 backend tests + clean frontend build**, tsc clean, backend↔frontend aligned, zero regressions.
