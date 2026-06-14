# GOLDEN BASELINE (grows with the build)

This is the list of passing tests and snapshot fixtures that must **never regress**. The regression
gate (`scripts/gate.sh`) fails if any test listed here is removed, skipped, weakened, or a snapshot
stops matching. Each phase appends its passing tests and any baseline snapshots here at phase close.

---

## Phase 0 — Protocol & scaffold

**Snapshot fixtures under `backend/tests/baseline/`:** none yet (the first is the P1 PAX metrics
payload — see below). **Baseline fixture #1 source data is in place:**
`backend/tests/fixtures/org_structure_PAX.csv` (ported byte-identical from legacy, md5
`4d17aa3cf70d9f4618571a5e99561f4c`) + `backend/tests/fixtures/expected_pax_metrics.json` (the
binding v1 numbers the P1 engine must reproduce).

**Passing tests (P0) — 13 total:**
- `test_smoke.py::test_health_endpoint` — FastAPI app boots and `/health` returns `{"status":"ok"}`.
- `test_smoke.py::test_mock_claude_returns_canned_json` — the `mock_claude` fixture makes
  `claude_service.complete(...)` return fixed JSON from `fixtures/sample_extract.json`, no network.
- `test_smoke.py::test_mock_claude_response_is_overridable` — a test can swap the canned response.
- `test_json_utils.py::*` (7 tests) — the ported JSON parse/repair helpers (`parse_ai_json`,
  `repair_truncated_json`, `extract_partial_data`) locked to legacy behaviour: fenced block, raw
  object, no-JSON error envelope, brace/bracket repair, balanced→None, truncated-no-brace→error,
  unbalanced-span→repaired+flagged, partial executive_summary extraction.
- `test_pax_fixture.py::test_pax_csv_present_and_shaped` — PAX CSV present, ID-keyed (Employee ID
  E001..E064), exactly 64 rows.
- `test_pax_fixture.py::test_expected_pax_metrics_match_spec` — recorded baseline numbers equal the
  binding v1/spec values (64 / 16 / 25.0 / 5,770,000 / 6).

**Frontend gate (P0):** `cd frontend && npm run build` completes with **zero** TypeScript errors.

---

## Phase 1 — Engagement core + diagnostics (COMPLETE)

**LOCKED PAX baseline (DECISIONS.md D9 — provided CSV is source of truth):**
`total_employees=64, total_managers=34, manager_ratio_pct=53.1, total_cost=6,620,000,
organizational_layers=6`. Recorded in `backend/tests/fixtures/expected_pax_metrics.json`.

**Snapshot fixture:** `backend/tests/baseline/pax_metrics.json` — the full deterministic
`calculate_all_metrics()` payload for the PAX CSV. `test_metrics.py::test_pax_metrics_snapshot_byte_stable`
asserts byte-stability.

**Passing tests (P1) — 33 backend total (10 from P0 + 23 new):**
- `test_models.py::*` (2) — engagement-core models + FK cascade purge.
- `test_migration.py::test_migration_upgrade_then_downgrade` — Alembic 001 additive + reversible.
- `test_csv_parser.py::*` (6) — ID-keyed parse, manager linkage, duplicate-name warning + intact
  tree, surrogate-key fallback, missing-column guard, locked-baseline metadata.
- `test_metrics.py::*` (3) — PAX metric parity, byte-stable snapshot, empty-positions guard.
- `test_diagnostics_service.py::*` (2) — typed-row flattening shape + headline values.
- `test_engagements_api.py::*` (4) — full diagnostic flow + PAX parity, two-engagement isolation,
  404 guards, purge cascade.
- `test_archetypes_activator.py::*` (3) — 7-archetype port, PAX activator triggers, endpoints.

**Frontend gate (P1):** `npm run build` zero TS errors; Engagements + Diagnostics pages ship.

> Additive-only from here: the engagement-core schema, migration 001, parser/metrics outputs, the
> `/api/v1/engagements` + `/api/v1/diagnostics` routes, and the locked PAX baseline must not regress.

## Phase 2 — Task Intelligence (COMPLETE)

**Reference seed (LOCKED counts for `taxonomy_seed.starter.json`):** sources=4, tasks=15,
overlays=3, crosswalks=6. Loader is idempotent; `desire_score → desire_score_us`;
`desire_score_local` NULL; the 0.40 crosswalk routes to `review_state=unreviewed`.

**Passing tests (P2) — 49 backend total (33 from P1 + 16 new):**
- `test_models_p2.py::*` (2) — reference/task models, logical overlay join (no FK), provenance cols.
- `test_migration.py::test_migration_002_*` — migration 002 additive + reversible (001 survives a
  single-step downgrade).
- `test_taxonomy_loader.py::*` (4) — starter counts, idempotency, dual-desire mapping, 0.40 routing.
- `test_task_extract.py::*` (3) — 500-position batching + deterministic merge + idempotency.
- `test_task_benchmark.py::*` (3) — benchmark statuses/routing, overlay join + robotics lever,
  **provenance-presence on every AI row** (A4 canonical-pipeline assertion).
- `test_task_intel_api.py::*` (3) — `/quick` key-free, AI-endpoint 400 guard, full pipeline via HTTP.

**Frontend gate (P2):** `npm run build` zero TS errors; Task Intelligence page ships.

> Additive-only from here: migration 002 tables, the seed loader contract, the task-intel pipeline
> outputs + `/api/v1/task-intel` routes, and the WORKBank/O*NET caveats must not regress.

## Phase 3 — Validation queue + local desire (COMPLETE)

**Passing tests (P3) — 54 backend total (49 from P2 + 5 new):**
- `test_validation_service.py::*` (3) — queue catches the seed's 0.40 crosswalk; bulk review +
  CURATED_BY_CONSULTANT crosswalk learning (idempotent); **client-ready excludes unreviewed
  model-inferred** (A4/M6).
- `test_validation_pulse_api.py::*` (2) — validation API (queue/review/stats + crosswalk learning);
  desire-pulse xlsx export + response import sets `desire_score_local` (~0.875) while
  `desire_score_us` is **never overwritten** (A4).

**Frontend gate (P3):** `npm run build` zero TS errors; Validation Queue page + pulse import ship.

> Additive-only from here: the validation queue/review/client-ready contract, the pulse
> import→local-desire recompute, and the `/api/v1/validation` + `/pulse` routes must not regress.

## Phase 4 — Scenario Studio (COMPLETE)

**Snapshot fixture:** `backend/tests/baseline/scenario_delta.json` — baseline/scenario/delta for a
fixed move sequence (DELETE E064 + ADD E999 $120k + REPARENT E003) on PAX. Delta: total_cost
+60,000, headcount 0, managers 0. `test_scenario_delta_snapshot.py` asserts byte-parity.

**Passing tests (P4) — 66 backend total (54 from P3 + 12 new):**
- `test_migration.py::test_migration_003_*` — migration 003 additive + reversible (earlier phases
  survive single-step downgrade).
- `test_scenario_engine.py::*` (6) — **apply/undo byte-parity**: no mutation, empty=identity, undo
  reproduces baseline metrics byte-identically, progressive undo, structural effects, merge/split.
- `test_scenarios_api.py::*` (4) — delta vs persisted baseline, present-lock + fork-to-edit, 3-way
  compare, 404 guard.
- `test_scenario_delta_snapshot.py::*` (1) — fixed-sequence delta snapshot parity.

**Frontend gate (P4):** `npm run build` zero TS errors; Scenario Studio page ships.

> Additive-only from here: the pure `apply_moves` contract, the scenario delta/compare/present/fork
> behaviour, the `/api/v1/scenarios` routes, and the scenario-delta snapshot must not regress.

## Phase 5 — Workflow Mapper + Transition Planner (COMPLETE)

**Passing tests (P5) — 70 backend total (66 from P4 + 4 new):**
- `test_migration.py::test_migration_004_*` — migration 004 additive + reversible.
- `test_workflow_transition_api.py::*` (3) — workflow process/step/map + L0–L3 opportunity matrix
  (mocked-AI priority); transition impact classes (augmented/new/unchanged) + pathway suggestions
  (model-inferred/unreviewed) + register xlsx export; AI-endpoint 400 key guard.
- `test_task_intel_api.py` extended — `GET /task-intel/tasks` lists extracted tasks (no key).

**Frontend gate (P5):** `npm run build` zero TS errors; Workflow Mapper + Transition Planner ship.

> Additive-only from here: migration 004 tables, the workflow/transition service contracts, the
> `/api/v1/workflows` + `/api/v1/transition` routes, and the register xlsx schema must not regress.

## Phase 6 — Deliverable Factory (COMPLETE)

**Passing tests (P6) — 74 backend total (70 from P5 + 4 new):**
- `test_migration.py::test_migration_005_*` — migration 005 additive + reversible.
- `test_deliverables_api.py::*` (3) — all 6 deliverable types generate valid files (PK/zip) with a
  provenance summary; **export-block** excludes unreviewed model-inferred from the AI roadmap and
  discloses the excluded count + caveats; unknown type → 400.

**Template:** modern-minimalist default (`deliverable_theme.MINIMAL`, D10); SATS theme stubbed.
**Frontend gate (P6):** `npm run build` zero TS errors; Deliverables page ships. Generated files go
to gitignored `backend/output/`.

> Additive-only from here: migration 005, the deliverable generators + provenance/export-block
> contract, and the `/api/v1/deliverables` routes must not regress.

## Pre-P7 Settings block (branding, UI-managed key, local-LLM) — COMPLETE

**Passing tests — 90 backend total (74 from P6 + 16 new):**
- `test_migration.py::test_migration_006_*` — migration 006 (`app_settings`) additive + reversible.
- `test_settings_service.py::*` (4) — DB persistence + cache, secret masking, unknown-key ignore,
  brand-palette JSON parse.
- `test_llm_provider.py::*` (4) — anthropic vs local routing, provider-aware `has_api_key`, missing
  key raises. (Local path uses `local_model` + `{base_url}/chat/completions`, httpx patched.)
- `test_settings_api.py::*` (5) — get/update (masked secret), brand-logo upload/fetch + bad-type
  reject, `test-llm` under current provider, 400 when unconfigured.
- `test_brand_deck.py::*` (2) — `template="brand"` records brand name + embeds logo; `minimal` default
  unchanged (regression).

**Frontend:** Settings page (provider/key/models/local + brand palette/logo + Test connection),
Deliverables template selector (minimal | brand), Settings tab. Builds zero TS errors.

> Provider routing preserves the prior Anthropic path (regression-proven). Brand assets live in
> gitignored `backend/uploads/brand/`. D11 supersedes A4 "Claude-only"; D12 extends D10.

## Reserved baseline targets (to be locked when their phase ships)

> Recorded now so a future session never forgets the byte-exact numbers it must reproduce.

**P1 — PAX fixture metrics (MUST match v1 exactly):**
- `total_employees = 64`
- `total_managers = 16`
- `manager_ratio_pct = 25.0`
- `total_cost = 5770000`
- `organizational_layers = 6`
(Plus: duplicate-name dataset parses with a warning and an intact, ID-keyed tree.)

**P2+:** one canonical response per new GET endpoint (shape + values, with mocked AI);
provenance-presence test (`source`, `confidence`, `review_state` on every AI-derived row).

**P3:** confidence < 0.70 → `unreviewed` routing test must catch the seed's 0.40 crosswalk row;
unreviewed items excluded from the canonical "client-ready" payload.

**P4+:** scenario delta payload for a fixed move sequence on the PAX fixture; apply/undo
byte-parity property test.
