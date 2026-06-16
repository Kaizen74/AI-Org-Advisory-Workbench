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
