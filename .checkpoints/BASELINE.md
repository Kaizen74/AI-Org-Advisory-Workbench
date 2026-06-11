# GOLDEN BASELINE (grows with the build)

This is the list of passing tests and snapshot fixtures that must **never regress**. The regression
gate (`scripts/gate.sh`) fails if any test listed here is removed, skipped, weakened, or a snapshot
stops matching. Each phase appends its passing tests and any baseline snapshots here at phase close.

---

## Phase 0 — Protocol & scaffold

**Snapshot fixtures under `backend/tests/baseline/`:** none yet (the first is the P1 PAX metrics
payload — see below).

**Passing tests (P0):**
- `backend/tests/test_smoke.py::test_health_endpoint` — FastAPI app boots and `/health` returns
  `{"status": "ok"}`.
- `backend/tests/test_smoke.py::test_mock_claude_returns_canned_json` — the `mock_claude` fixture
  monkeypatches the Anthropic client so `messages.create(...).content[0].text` is the fixed JSON
  from `backend/tests/fixtures/sample_extract.json`, parsed with no network call.

**Frontend gate (P0):** `cd frontend && npm run build` completes with **zero** TypeScript errors.

---

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
