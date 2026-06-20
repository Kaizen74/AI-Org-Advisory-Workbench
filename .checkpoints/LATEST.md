# LATEST CHECKPOINT
**Updated:** 2026-06-16T12:50:00 (P7 + D13 + bugfixes D14–D16 + refocus D17; live deploy still pending Eric)
**Phase:** P7 done + access-control (D13) + D14–D16 fixes + **D17 product refocus**. **All seven phases
P0–P7 built; app is private and now centred on role→task→AI-potential (H0–H5).**
**Last completed micro-task:** D27 — WORKBank clone guidance: clone HF dataset into ./workbank as a git-ignored BUILD INPUT (never commit raw data, A4); commit only the curated overlay. Added /workbank/ to .gitignore; converter now finds CSVs recursively (HF nested layout); --src defaults to ./workbank. HF clone still 403 in sandbox (allowlist needed). Gate GREEN (131 tests + build).
**Prior micro-task:** D26 — hardened WORKBank ingestion: converter extracted to importable app/services/workbank_ingest (unit-tested offline with synthetic CSVs; CLI is now a thin wrapper) + rollup `source_mix` {overlay/ai_inferred/robotics/unclassified} with a Task Intelligence 'Benchmark coverage' card so reliance on inference is measurable; proved overlay-backed tasks bypass inference. HF still not allowlisted in sandbox (403) — allowlist + run the script to go live. Gate GREEN (130 tests + build).
**Prior micro-task:** D25 — WORKBank integration path (HF-hosted tables; HF not allowlisted here): scripts/build_workbank_overlay.py + additive taxonomy_loader hook (workbank_overlay.curated.json → authoritative overlay) so real values drop in once HF is reachable; layered authority curated>WORKBank>Claude inference. Also fixed lingering robotics levers — infer-potential re-bands auto ROBOTICS_GSE_LEVER rows via the HAS rubric (idempotent). Gate GREEN (128 tests + build).
**Prior micro-task:** D24 — robust AI benchmarking: unmatched tasks (NO_BENCHMARK_MATCH) are now scored by Claude grounded in the WORKBank HAS rubric (infer_unmatched_potential + POST /task-intel/infer-potential; model-inferred/unreviewed → export-blocked; idempotent). Pipeline adds the step; AIInferResult type + api.inferPotential. Decided AGAINST live O*NET/ESCO/WORKBank API wiring (static dataset / keys / 200MB guardrail). Gate GREEN (126 tests + build).
**Prior micro-task:** D23 — (1) Reset board now clears all mappings (POST /workflows/{id}/reset-board; active when mapped_count>0); (2) delete client/engagement/dataset (DELETE routes + thorough cascade + Engagements ✕ buttons); (3) scoring no longer mislabels unmatched knowledge work as robotics — new NO_BENCHMARK_MATCH zone vs ROBOTICS_GSE_LEVER, queue label + H0 rubric clarified. Gate GREEN (125 tests + build).
**Prior micro-task:** D22 — added the 'Finalized workflow' deliverable (PPTX_WORKFLOW): per process, builds a deck from the real board (steps → mapped tasks `text [role · H-band]`, per-step H0–H5 mix, mapped/unmapped line) + provenance; registered backend + frontend button. Gate GREEN (122 tests + build).
**Prior micro-task:** D20 — integrated the visual Workflow & Task-analysis Mapper (drag-to-remap board: Flow/Landscape/Roll-up, hover role-trace, undo, inspector). Backend (additive, no migration): board/move_task/unmap_task + GET /board, POST /move-task, /unmap-task; board rows carry real fields + headline human_agency_level (H0–H5) + has_level + HAS rubric. Frontend: BoardTask/Step/WorkflowBoard types, api.workflowBoard/moveTask/unmapTask, WorkflowMapper replaced and refined to H0–H5 (L0–L3 secondary). Gate GREEN (121 tests + build).
**Prior micro-task:** D21 — dropped the scenario deck: centralized `SHOW_SIMULATION` into `src/config.ts` (App.tsx + Deliverables.tsx) and gated the scenario-comparison + transition-register deliverables behind it; Deliverables now offers only Diagnostic/AI-roadmap/TOM/Metrics. Backend intact (reversible). Gate GREEN (121 tests + build).
**Prior micro-task:** D19 — re-banded the Workflow Mapper AI-opportunity matrix to H0–H5 (agency_matrix / per-step agency_counts / agency_evidencing / rubric; L0–L3 kept internally; UI grid + evidencing now H0–H5). Gate GREEN (118 tests + build).
**Prior micro-task:** D18 — Workflow Mapper: matrix 'Run' progress (spinner + Running…), a new Mapping coverage card (progress bar + linked/unlinked/empty-step tiles + what's-left/what's-missing lists; `list_steps` now returns `linked_task_ids`), and a note that processes/steps are authored labels onto which CSV tasks are linked. Gate GREEN (118 tests + build).
**Prior micro-task:** D17 — parked Scenario Studio + Transition Planner behind `SHOW_SIMULATION`
(reversible nav flag; code+tests intact) and made the **WORKBank Human Agency Scale (H0–H5)** the headline
AI-potential metric (`human_agency_band` + `HUMAN_AGENCY_SCALE` rubric; rollup `agency` breakdown; queue
ai_score band; Task Intelligence headline chart+legend). L0–L3 kept internally. Gate GREEN (118 tests + build).
**In-flight micro-task:** D28 (BLOCKED on environment) — load the real WORKBank overlay. The ingestion
path (D25–D27) is complete and green; the ONLY blocker is network egress: `huggingface.co` / `hf.co` /
`cdn-lfs*.huggingface.co` are not in this container's allowlist (clone returns HTTP 403). Egress rules
apply at session creation, so a NEW session is required after the allowlist is updated.
**RESUME HERE (new session) — load WORKBank, exact steps:**
  1. Confirm HF reachable: `curl -sL -o /dev/null -w "%{http_code}\n" https://huggingface.co` → expect 200.
     (If 403, the allowlist didn't take effect — needs HF + the LFS CDN hosts, then a fresh session.)
  2. `cd /home/user/AI-Org-Advisory-Workbench && git clone https://huggingface.co/datasets/SALT-NLP/WORKBank workbank`
     (`workbank/` is gitignored — build input only, never commit the raw dataset).
  3. `cd backend && source .venv/bin/activate && cd ..` then
     `python scripts/build_workbank_overlay.py` (defaults --src ./workbank; finds CSVs recursively).
     → writes `backend/app/resources/taxonomies/workbank_overlay.curated.json` (commit THIS only).
  4. Sanity check the output row count + a sample row; consider `--limit` to keep the subset small (A4).
  5. Run the gate: `bash scripts/gate.sh`. The loader auto-promotes the curated overlay to the
     authoritative layer; re-running Task Intelligence shows the Benchmark-coverage card shift from
     "AI-inferred" to "Curated / WORKBank".
  6. Commit `workbank_overlay.curated.json` + memory updates (DECISIONS/PROGRESS/LATEST/CLAUDE) as D28; push.
**Next action (be exact):** Two things remain, both needing Eric (cannot be done from this sandbox):
  1. **Live deploy** — follow README §4 to deploy backend→Railway (root `backend`, add Postgres, set
     `DATABASE_URL` with `+asyncpg`, `ANON_SALT`, **`AUTH_SECRET`, `ACCESS_USERS=you@email:passcode`**,
     start command/Procfile) and frontend→Vercel (root `frontend`, set `VITE_API_BASE_URL` to the
     Railway URL), then set `CORS_ORIGINS` on Railway to the Vercel URL. Sign in with your
     `ACCESS_USERS` login, then enter the Anthropic key + add other users in Settings.
  2. **Verify the README verbatim** from a clean machine (local run + deploy) per B5 #10; capture any
     wording corrections (actual Vercel/Railway button names) back into README §4.
  Optional follow-ups (additive): branch merge to `main` (then delete `legacy v1 app.zip` from main);
  expand audit UI; refine activator/L0-L3 rubrics if Eric supplies definitions.
**Test status:** PASS — gate GREEN, **131 backend tests + clean frontend build**, zero regressions.
**Recovery commands:** `bash scripts/gate.sh`
**Open questions for Eric:**
  1. **Live cloud deploy** needs your Vercel + Railway accounts connected to the GitHub repo — say
     when you want to do it and I'll walk you through (or adjust README §4 to the exact screens).
  2. Branch `claude/compassionate-knuth-wx5bjq` holds P0–P7. Merge to `main` when ready; then you can
     delete `legacy v1 app.zip` from `main` (this branch carries the unpacked `legacy/`).
  3. (Optional) Five-Activator labels, L0–L3 rubric, impact-class mapping are heuristic placeholders —
     send preferred definitions for a precise (additive) wiring.
