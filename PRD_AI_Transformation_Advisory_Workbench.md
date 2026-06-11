# PRD — OrgAI Advisory Workbench (working name)

**Version:** 1.2
**Author:** Eric Yim (with Claude)
**Date:** 11 June 2026
**Status:** For review
**Predecessor:** `claude-org-design-analyzer` (v1 diagnostic app) + `WORKFORCE_INTELLIGENCE_SPEC_FINAL.md` v1.1
**Companions (build-time):** `BUILD_SPEC_ADVISORY_WORKBENCH.md` (executable spec for Claude Code; Part A implements §12); `taxonomy_seed.starter.json` (reference-data starter — `_meta` warnings are binding); `WORKFORCE_INTELLIGENCE_ARCHITECTURE.md` (legacy module architecture — layering and logical-overlay-join decisions carry over)
**Changelog v1.1:** Added §12 (Build resilience & regression protocol): interruption-proof persistent memory and mandatory mock-test regression gates after every phase and every fix; updated §7 and §11.
**Changelog v1.2:** Incorporated the confirmed taxonomy seed + WI architecture companions. M2 now specifies the seed `desire_score` → `desire_score_us` loader mapping, the occupation-level vs task-statement-level O*NET join caveat, and confidence-thresholded routing of even CURATED crosswalks into the validation queue. Codebase hosted at the private GitHub repo `Kaizen74/AI-Org-Advisory-Workbench` with push-on-commit resilience, data-hygiene rules, and a binding non-technical README specification (spec B7: local run + Vercel/Railway deploy, click-by-click, verified by following it verbatim).

---

## 1. Problem statement

### 1.1 The business problem

Eric offers AI transformation advisory services across three connected disciplines: **job redesign**, **AI workflow design**, and **organization design / target operating model (TOM)**. The current tooling (v1 app) supports only one slice of one discipline: single-org, current-state diagnostics. Everything else — future-state design, scenario comparison, AI-opportunity validation, workforce transition planning, and client deliverable production — is done manually, costing 60–80% of engagement hours and producing inconsistent artefacts.

### 1.2 What the v1 app proved

- Structural metrics from a CSV org file are computable, reliable, and client-credible (graph-based span/layer/cost/grade-gap engine, validated against the PAX fixture).
- Grounding Claude in embedded reference data (7-archetype rubric; SFw/O*NET/WORKBank taxonomies) produces defensible AI analysis; ungrounded one-shot prompts do not.
- Provenance tagging (SFw / O*NET / WORKBank / model-inferred) is the right transparency mechanism and must be preserved.

### 1.3 What the v1 app cannot do (the gap)

| # | Gap | Advisory consequence |
|---|-----|---------------------|
| G1 | No client/engagement/scenario entities | Cannot manage multiple clients or compare design options |
| G2 | Diagnostic only — no design surface | The fee-earning redesign work happens outside the tool |
| G3 | AI inferences are never consultant-validated | Cannot defend AI-mapped tasks/zones in front of a client |
| G4 | No deliverable export | Insights re-keyed manually into branded decks |
| G5 | Name-keyed org graph; JSON-blob results | Breaks at enterprise scale; nothing is queryable or trendable |
| G6 | No data-protection posture | PDPA blocker for any non-SATS client data |
| G7 | Single-prompt pipeline with context ceiling | Fails beyond a few hundred positions |

---

## 2. Product vision

> **One workbench that takes an engagement from raw HR data to a validated, client-ready TOM and AI transformation roadmap — with every AI inference traceable to a source and approved by a human consultant before it appears in a deliverable.**

### 2.1 Design principles (non-negotiable, carried over and extended)

1. **Provenance on everything.** Every score, mapping, benchmark, and recommendation carries a source tag and a confidence value. Regulator-backed (SFw) ≠ research-backed (WORKBank) ≠ model-inferred — and US-derived preference data is always labelled as a hypothesis to validate locally.
2. **Human-in-the-loop is a workflow, not a disclaimer.** Model-inferred items enter a *review queue*; nothing model-inferred reaches a client deliverable in `unreviewed` state.
3. **Follow the work (Kates-Kesler).** The unit of analysis descends from org box → position → task → process. Rollups go both up the org graph *and* across value streams.
4. **Engagement-centric, scenario-based.** All data hangs off an Engagement; every design exists as a named Scenario that can be diffed against baseline and against other scenarios.
5. **Deliverable-first.** Every analysis screen has an "Export" path to branded pptx/docx/xlsx. If it can't be exported, it isn't done.
6. **Lightweight deployment.** No heavy ML weights; Claude API for inference; SQLite→Postgres-ready schema; fits Vercel/Railway free-tier constraints.
7. **Checkpoint-resilient build.** Part A of the WI spec (CLAUDE.md protocol, golden baselines, additive-only changes, mocked AI tests, regression gates) applies verbatim to this build.

---

## 3. Users & jobs-to-be-done

| User | Jobs |
|------|------|
| **Lead consultant (Eric)** | Set up engagement; upload data; run diagnostics; design scenarios; validate AI inferences; generate deliverables |
| **Client sponsor (e.g., CHRO/CCO)** | View read-only dashboards in workshops; react to scenario comparisons live |
| **Future associate consultant** | Run analyses within an engagement Eric owns; cannot export unreviewed content |

Primary JTBD chain: **Diagnose → Benchmark tasks → Score AI opportunity → Validate → Design scenarios → Plan transition → Deliver.**

---

## 4. Functional requirements (modules)

### M0 — Engagement Hub *(new; fixes G1)*

- Create **Client** → **Engagement** → one or more **Datasets** (org CSV uploads) and **Scenarios**.
- Engagement record holds: industry, strategy context documents, design criteria, taxonomy defaults (e.g., SFw Air Transport for SATS), anonymization setting.
- Dataset versioning: re-uploads create a new version; analyses pin to a version.
- **Acceptance:** two engagements with different clients coexist; deleting an engagement cascades only its own data.

### M1 — Diagnostic Engine *(carried over, hardened; fixes G5 partially)*

- Port the v1 metrics engine (spans, layers, manager ratio, cost, grade gap, health indicators) **with one breaking fix: graph keyed on `Employee ID`**, falling back to a generated surrogate key, never on name. Name collisions raise a validation warning listing duplicates.
- Metrics persist as **typed rows** (metric, unit, value, dataset version), not a JSON blob — so they are queryable and trendable across datasets and engagements.
- Archetype scoring carried over with the embedded 7-archetype rubric.
- New: **Kates-Kesler activator pre-screen** — map computed metrics + Work Activities signals to the Five Activators as leading-indicator flags (layer bloat → Activator 1; coordination gaps → Activator 2; etc.), referencing the Observable Outcomes indicator framework already drafted for SATS.
- **Acceptance:** PAX fixture returns identical metric values to v1 baseline; a dataset with two "Tan Wei Ming" rows parses with a warning and an intact tree.

### M2 — Task & Job Intelligence *(adopts WI spec v1.1 with two upgrades; fixes G3, G7)*

Implements the WI spec pipeline (extract → benchmark vs SFw/O*NET → WORKBank HAS/zone overlay → L0–L3 AI opportunity → rollup), with:

- **Upgrade 1 — Validation queue (the trust loop).** Every model-inferred mapping (task→SFw match, task→O*NET code, inferred zone, inferred HAS) lands in a review screen: *Approve / Edit / Reject*, bulk actions, filter by confidence. Approved items get `method: CURATED_BY_CONSULTANT` and feed back into the crosswalk table — the system gets more accurate per engagement. Deliverables include only `SFw`, `WORKBank`, or `consultant-approved` items by default (toggleable with a visible caveat banner).
- **Upgrade 2 — Batched extraction.** Extraction and benchmarking run **per department (or per ~40 positions)** in parallel batches, then merge — removing the single-prompt context ceiling. Deterministic merge tested against a 500-position synthetic fixture.
- **Local desire capture.** A lightweight pulse instrument (exportable as xlsx or a shareable form) collects the *client workforce's* automation-desire ratings on the top-N tasks, producing a local desire score that sits beside (never overwrites) the WORKBank US score. The seed loader maps the starter file's single `desire_score` into `desire_score_us`; `desire_score_local` is populated only by this instrument. This operationalizes the "US data is a hypothesis" caveat instead of just stating it.
- **Confidence-thresholded review routing.** Any task mapping with confidence < 0.70 enters the validation queue as `unreviewed` — *including* curated seed crosswalks (the starter ships one at 0.40). Review is triggered by confidence, not source label.
- **O*NET granularity caveat (binding verification item).** The starter seed joins at O*NET *occupation* level; real WORKBank data is keyed at *task-statement* level. Occupation-level joins smear one HAS/zone value across all of a role's tasks — acceptable for illustration, flagged in every payload's caveats, and refined to task-statement codes before any client-facing use.
- All v1.1 data-validity guardrails are binding: HAS and capability stay independent; physical tasks carry no software-agent overlay and are surfaced as robotics/GSE levers.

### M3 — Scenario Design Studio *(new; fixes G2 — the core new value)*

The redesign surface. A Scenario = baseline dataset + an ordered list of **design moves**:

- Move types v1: *merge units, split unit, re-parent unit/position, delete position, add position, change grade, reassign tasks between roles, designate anchor layer, mark docking station.*
- Live **delta panel** vs baseline: headcount Δ, cost Δ, span/layer Δ, manager ratio Δ, AI-opportunity exposure Δ (% of task-hours in L2/L3), HAS profile shift.
- **Side-by-side comparison** of up to 3 scenarios on one screen (the workshop money-shot).
- Each move carries a free-text **rationale** field (feeds the deliverable narrative) and an optional activator tag (which of the Five Activators it serves).
- Scenarios are immutable once marked *Presented*; further edits fork a new version.
- **Acceptance:** applying and undoing any move sequence returns byte-identical baseline metrics; comparison view renders 3 scenarios for a 1,000-position org in < 3 s.

### M4 — AI Workflow Mapper *(new)*

Bridges job redesign to AI workflow advisory:

- Define **processes/value streams** and attach tasks (from M2) to process steps — the "follow the work" view across org boxes.
- Per process, generate the **four-level AI opportunity matrix** (L0 Manual → L1 Assisted → L2 Enabled → L3 Reinvention) — porting the existing `ai-opportunity` skill logic — with complexity/priority scoring and the specific tasks evidencing each level.
- Output: a prioritized AI workflow roadmap per process, with which roles change and how (links back into M3 task-reassignment moves).

### M5 — Workforce Transition Planner *(new)*

- For each scenario, compute **role impact classes**: unchanged / augmented (tasks shift to L1–L2) / transformed (L3 or major task reassignment) / displaced / new.
- Map skill gaps using SFw skills attached to taxonomy tasks → suggested **SkillsFuture-aligned reskilling pathways** (a genuine differentiator for Singapore clients; pathway suggestions are model-inferred and pass through the M2 validation queue).
- Export a transition register (xlsx): position, impact class, skill gaps, suggested pathway, provenance.

### M6 — Deliverable Factory *(new; fixes G4)*

- One-click export per module: **branded pptx** (diagnostic read-out; scenario comparison; AI roadmap), **docx** (TOM narrative report), **xlsx** (metrics pack; transition register).
- Template system: client logo, palette, disclosure page auto-listing all caveats + provenance summary (% of content by source tag) — transparency as a feature.
- Hard rule: export blocks (or banners) any unreviewed model-inferred content per M2.

### M7 — Trust, Security & Administration *(new; fixes G6)*

- **Anonymization mode** per engagement: names hashed to stable pseudonyms at ingest; real names stored in a separable lookup that can be excluded from any export and purged on demand.
- Engagement-level data purge (PDPA "right to deletion" support); audit log of uploads, AI calls, validations, exports.
- API keys and model choice in server config, not the database; model string configurable per environment (no hardcoding).
- Roles: Owner / Consultant / Client-viewer (read-only dashboards, no raw data).

---

## 5. Data model (conceptual)

```
Client ──< Engagement ──< Dataset(version) ──< Position ──< Task
                      │                              │
                      ├──< Scenario ──< DesignMove   ├──< TaskBenchmark (source, status, confidence, review_state)
                      │         └──< ScenarioMetric  └──< TaskAIScore  (has_level, zone, desire_us, desire_local,
                      ├──< Process ──< ProcessStep ──< TaskLink          capability, ai_level, source, review_state)
                      ├──< Deliverable (type, template, content_hash, provenance_summary)
                      └──< AuditEvent
Reference layer (global, engagement-independent — carried over from WI spec):
TaxonomySource ──< TaxonomyTask ──< TaxonomyCrosswalk ; TaskAIOverlay (WORKBank)
```

Key changes vs v1: positions and tasks are **rows, not JSON**; every AI-derived row carries `source`, `confidence`, `review_state` (`unreviewed | approved | edited | rejected`); all engagement data is FK-cascaded for clean purge.

---

## 6. AI architecture

- **Staged, batched pipeline** — separate, smaller calls for extract / map / score / synthesize, each with grounded reference context injected (taxonomy subset relevant to the batch), strict-JSON output, shared parse/repair util. No single mega-prompt.
- **Model-agnostic config**: default Sonnet-class for extraction/mapping, Opus/Fable-class for executive synthesis; model strings in env config.
- **Determinism for tests**: every Claude call monkeypatchable; canned fixtures; full suite runs offline (carried from WI spec A3).
- **Confidence discipline**: the model must emit a confidence value and cite which taxonomy row(s) grounded each mapping; mappings with no grounding row are auto-tagged `model-inferred` + `unreviewed`.

---

## 7. Non-functional requirements

| Area | Requirement |
|------|-------------|
| Scale | 50,000 positions per dataset; batched AI pipeline; rollups computed in SQL/pandas, not in prompts |
| Performance | Diagnostic metrics < 10 s for 50k positions; scenario delta < 3 s for 1k positions |
| Deployment | Frontend Vercel; backend Railway/Render; SQLite dev → Postgres prod via same SQLAlchemy models; no torch/transformers |
| Security | Anonymization at ingest (optional per engagement); encrypted at rest in prod (Postgres + disk encryption); purge & audit per M7 |
| Build protocol | Interruption-proof, regression-gated build per Section 12, codified as Part A of `BUILD_SPEC_ADVISORY_WORKBENCH.md` (CLAUDE.md auto-loaded protocol, micro-task checkpointing, golden baselines, mocked-AI tests, full gate after every phase and every fix) |

---

## 8. Phased delivery

| Phase | Scope | Exit criteria |
|-------|-------|---------------|
| **P0** | Repo scaffold, CLAUDE.md, schema for Client/Engagement/Dataset/Position, ID-keyed parser port | PAX fixture parses; duplicate-name warning test passes |
| **P1** | M1 Diagnostic engine port (typed metrics) + M0 Engagement Hub UI | v1 metric parity on PAX; two-engagement isolation test |
| **P2** | M2 Task intelligence (WI pipeline, batched) + reference seed loader | 500-position synthetic fixture completes; provenance on every row |
| **P3** | M2 Validation queue + local desire capture | No unreviewed item exportable; approval feeds crosswalk |
| **P4** | M3 Scenario Studio (moves, deltas, 3-way comparison) | Undo-to-baseline byte-parity test; workshop comparison screen |
| **P5** | M4 Workflow Mapper + M5 Transition Planner | AI roadmap + transition register generated for sample org |
| **P6** | M6 Deliverable Factory (pptx/docx/xlsx, SATS-brand template first) | One-click branded diagnostic deck from live data |
| **P7** | M7 Security hardening, anonymization, purge, audit, Postgres deploy | PDPA checklist green; deployed demo environment |

Each phase ends with the regression gate and checkpoint update; the v1 app stays running untouched as the fallback throughout.

---

## 9. Out of scope (v1 of this app)

- Local embedding models / TechWolf JobBERT (remains the documented "rigour upgrade" path).
- Full O*NET / SkillsFuture / ESCO ingestion (curated subsets only).
- Real-time multi-user co-editing of scenarios.
- HRIS API integrations (CSV ingest only in v1).
- Automated ONA / calendar-analytics ingestion (the Observable Outcomes leading indicators remain a manual-input pack in v1).

---

## 10. Success metrics

| Metric | Target |
|--------|--------|
| Engagement hours saved on diagnostic + deliverable production | ≥ 50% vs current manual baseline |
| % of client-facing AI inferences consultant-reviewed before export | 100% (enforced) |
| Time from data receipt to first client-ready diagnostic deck | ≤ 2 working days |
| Scenarios compared live in a client workshop | ≥ 2 per design engagement |
| Provenance disclosure present in every deliverable | 100% (auto-generated page) |

---

## 11. Key risks & mitigations

| Risk | Mitigation |
|------|------------|
| Scope creep — seven modules is a platform | Phases ship independently; P1–P3 alone already exceed v1's value; stop/ship decision at each gate |
| AI mapping quality below client bar | Validation queue + grounded prompts + crosswalk learning; never ship unreviewed inference |
| WORKBank/US-data misuse | Local desire capture instrument; dual-score display; binding caveats auto-rendered |
| Solo non-technical builder; sessions cut off by plan limits | Section 12 protocol: repo-resident memory, ≤30-min micro-tasks, checkpoint+commit after every task — worst-case loss is one partial micro-task |
| Client data exposure | Anonymization at ingest, purge function, audit log before any second-client engagement |

---

## 12. Build resilience & regression protocol (binding)

This section is a **product requirement**, not a development nicety: the builder is non-technical
and build sessions are routinely interrupted without warning by Claude plan limits. The full
executable rules live in Part A of `BUILD_SPEC_ADVISORY_WORKBENCH.md`; the PRD-level requirements
are:

### 12.1 Persistent memory — the repo is the memory

- **R12.1** All build state lives in version-controlled files, never only in a conversation:
  `CLAUDE.md` (auto-loaded protocol + current-state summary), `PROGRESS.md` (append-only journal),
  `.checkpoints/LATEST.md` (current phase, last completed task, in-flight task, exact next action,
  test status, recovery commands), `.checkpoints/DECISIONS.md` (append-only decision log),
  `.checkpoints/BASELINE.md` (the growing golden baseline).
- **R12.2** Work is decomposed into **micro-tasks of ≤ 30 minutes**. After every completed
  micro-task: tests run, work committed, `LATEST.md` updated. An abrupt cut-off can therefore lose
  at most one partial micro-task, and `LATEST.md` documents how to finish it.
- **R12.3** Every session begins with a fixed ritual (read memory files → reconcile against
  `git log`/`git status` → run the regression gate → state the resuming task) and ends with a
  fixed ritual (park or finish in-flight work → full gate → update all memory files → commit).
  Resume requires only pasting a standard prompt (`CLAUDE_CODE_PROMPTS.md`, Prompt 2).

### 12.2 Mock testing & regression gates — no silent breakage

- **R12.4** The Claude API is **mocked in all tests from day one**; the suite runs offline,
  deterministically, and at zero API cost.
- **R12.5** A **golden baseline grows with the build**: each phase appends its passing tests and
  snapshot fixtures (starting with the v1 PAX metric values) that later phases must reproduce
  byte-identically.
- **R12.6** A single-command **regression gate** (backend suite + baseline parity + clean frontend
  TypeScript build) must pass at session start, after every phase, after **every bug fix**, and at
  session end. A phase or fix that leaves the gate red is, by definition, not done.
- **R12.7** **Fix protocol:** every bug fix begins with a failing test reproducing the bug, ends
  with the full gate green, and permanently adds that test to the suite — so the same bug cannot
  silently return and the fix is proven not to have caused unintended consequences elsewhere.
- **R12.8** Completed-phase code is **additive-only** thereafter: no signature, route, schema, or
  behaviour change to a finished module without a logged decision and regression tests proving
  prior behaviour is preserved.
