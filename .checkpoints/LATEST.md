# LATEST CHECKPOINT
**Updated:** 2026-06-11T01:30:00 (Phase 1 — IN PROGRESS, parked on a data conflict)
**Phase:** P1 — Engagement core + diagnostics
**Last completed micro-task:** P1.4 — ported the CSV parser with the breaking fix (Employee-ID
keyed graph + surrogate fallback + duplicate-name warning). Faithful: reproduces legacy v1 output on
the PAX CSV exactly. 22 backend tests green. (P1.1 DB layer, P1.2 models, P1.3 migration 001 also
done and committed.)
**In-flight micro-task:** P1.5 (metrics engine port + PAX parity baseline) is **PARKED** pending the
data conflict in Open Question #1 below — do not lock a parity baseline until Eric resolves it.
**Next action (be exact):**
  * IF Eric says "use the provided CSV as truth" → set the P1 parity target to the actual values
    (total_employees=64, total_managers=34, manager_ratio_pct=53.1, total_cost=6,620,000,
    organizational_layers=6); update `backend/tests/fixtures/expected_pax_metrics.json` + the
    `test_pax_fixture.py`/`test_csv_parser.py` asserts accordingly; then port the metrics engine
    (`legacy/.../metrics_service.py`) to typed `metric_values`, add the parity test, snapshot the
    payload under `backend/tests/baseline/`, and resume P1.6→P1.12.
  * IF Eric uploads the correct PAX CSV (yielding 16 / 25.0 / 5,770,000) → replace the fixture, keep
    the spec's parity numbers, then continue P1.5 as originally specified.
**Test status:** PASS — gate GREEN, 22 backend tests + clean frontend build. (No baseline locked
yet for PAX metrics — deliberately deferred.)
**Recovery commands:** `bash scripts/gate.sh`
**Open questions for Eric:**
  1. **BLOCKER for P1 parity — the PAX CSV doesn't match the spec's parity numbers.** Running the
     faithful port (and the legacy v1 code itself) on the `org_structure_PAX.csv` inside your
     `legacy v1 app.zip` gives **64 employees, 34 managers (53.1%), $6,620,000 cost, 6 layers**. The
     Build Spec's P1 parity target is **64 / 16 / 25.0 / 5,770,000 / 6**. Only employees (64) and
     layers (6) match. Since total_cost is just a salary sum and this CSV sums to 6,620,000, it is a
     *different file* than the one the spec (and the legacy app's own tests) were validated against.
     **Choose: (A) treat this CSV as the source of truth and I reset the parity target to the actual
     numbers, or (B) upload the correct PAX CSV that yields 16 / 25.0 / 5,770,000.** I parked the
     parity-baseline step rather than fabricate numbers.
  2. (Housekeeping, no action now) Your `legacy v1 app.zip` is on `main`; this branch carries the
     unpacked `legacy/` folder. You can delete the zip from `main` after this branch merges.
