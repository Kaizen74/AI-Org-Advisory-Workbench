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

## 2026-06-11 — D7: `_json_utils` port keeps the legacy raw-JSON contract (closing-brace required)

**Source:** Port of `work_activities_service._parse_response` into `app/services/_json_utils.py`.
**Decision:** Preserve the legacy behaviour exactly: `parse_ai_json` only attempts truncated-JSON
repair when the extracted span contains a closing `}`; a string with no `}` short-circuits to the
`{"error": "Could not parse response"}` envelope rather than being repaired. **Rationale:** Faithful
ports must not silently "improve" behaviour (Part A additive-only / no-silent-change). Tests in
`test_json_utils.py` lock this contract so a future phase cannot regress it. (A test I first wrote
asserted the wrong expectation; the test was corrected, not the ported code.)
