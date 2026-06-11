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
