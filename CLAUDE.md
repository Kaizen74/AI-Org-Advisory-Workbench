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

**Pre-P7 Settings block (2026-06-14 — COMPLETE):** Added an `app_settings` table (migration 006) +
`settings_service` + `/api/v1/settings` so the **Anthropic API key is managed via the UI** (masked),
the **LLM provider can switch to a local OpenAI-compatible endpoint** for frontier-outage fallback
(D11 — `claude_service.complete` now routes by provider via httpx, public signatures preserved), and
the **brand logo + palette are swappable and drive the deck template** (`template="brand"`, D12). New
**Settings** frontend page + Deliverables template selector. **Gate GREEN: 90 backend tests + clean
frontend build, zero regressions.** Next: **Phase 7 (Security & deploy)** on Eric's go-ahead.

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
