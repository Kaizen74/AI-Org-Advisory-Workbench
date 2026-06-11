# Claude Code Prompts — copy and paste exactly

## PROMPT 1 — Kickoff (use ONCE, in your first Claude Code session)

Paste this after you have created the project folder and placed the three files inside it
(see "Before you start" at the bottom of this document):

---

You are building a new application called the OrgAI Advisory Workbench. These documents in this
folder govern everything you do:

1. BUILD_SPEC_ADVISORY_WORKBENCH.md — read Part A (operating protocol) FIRST and in full. It is
   mandatory and non-negotiable. Then read Part B (requirements).
2. PRD_AI_Transformation_Advisory_Workbench.md — the product requirements and rationale.
3. WORKFORCE_INTELLIGENCE_ARCHITECTURE.md — legacy architecture; read in Phase 0 per spec B0
   (two decisions carry over, one is superseded — record all three in DECISIONS.md).
4. taxonomy_seed.starter.json — reference data for Phase 2; its _meta warnings are binding.

Critical context: I am non-technical, and my sessions with you WILL be interrupted without
warning by plan limits. The protocol in Part A exists so that no work or context is ever lost:
you must checkpoint after every micro-task, commit constantly, push every commit to the GitHub
remote (this folder is a clone of https://github.com/Kaizen74/AI-Org-Advisory-Workbench), and
keep .checkpoints/LATEST.md accurate at all times, so any future session can resume exactly
where you stopped.

Your first actions, in order:
1. Read both governing documents fully (spec Part A first).
2. Execute Phase 0 exactly as specified in Part B (B4): copy Part A into CLAUDE.md, create the
   checkpoint files, set up .gitignore BEFORE any commit so no database/client/.env files can
   ever reach GitHub, create the README stub per spec B7 (written for a non-technical owner),
   verify the legacy/ folder and both companion files exist, scaffold the project, set up the
   mock_claude test fixture and the gate script, then make the first push to GitHub.
3. If anything is missing or ambiguous, STOP, write the question into LATEST.md under
   "Open questions for Eric", and ask me before proceeding.
4. At the end of Phase 0, run the regression gate, update all checkpoint files, commit, push, and
   report to me in plain language: what was built, gate status, confirmation the push succeeded,
   and the next micro-task.

Do not skip ahead. Do not start Phase 1 until I confirm Phase 0 looks good.

---

## PROMPT 2 — Resume (use at the START of EVERY later session)

---

Resume work on the OrgAI Advisory Workbench. Follow the session-start ritual in CLAUDE.md
Part A exactly:

1. Read CLAUDE.md, .checkpoints/LATEST.md, .checkpoints/DECISIONS.md, and the current phase
   section of PROGRESS.md.
2. Run git log --oneline -15 and git status; reconcile any uncommitted work against the
   in-flight block in LATEST.md.
3. Run the regression gate (scripts/gate.sh). If anything is red, fixing it is your first task,
   using the Fix Protocol (failing test first, then fix, then FULL gate).
4. Tell me in one sentence which phase and micro-task you are resuming, then proceed.

Remember: checkpoint and commit after every micro-task. Assume this session can be cut off at
any moment. Park work cleanly and early if needed — never leave LATEST.md stale.

---

## PROMPT 3 — Bug fix (use whenever you find something broken while testing the app)

---

Bug report: [describe what you did, what you expected, and what actually happened — screenshots
or error text help].

Apply the Fix Protocol from CLAUDE.md Part A, Rule 4, literally:
1. Write a failing test that reproduces this bug first.
2. Implement the minimal fix.
3. Run the FULL regression gate — the fix is not done until the entire suite and all baseline
   parity checks pass, proving nothing else broke.
4. Commit with the fix(...) message format, update LATEST.md, and report: cause, fix, the name
   of the new regression test, and full gate status.

---

## Before you start (one-time setup, click by click)

1. Make sure your GitHub repo `Kaizen74/AI-Org-Advisory-Workbench` is set to **Private**
   (on GitHub: repo page → Settings → scroll to "Danger Zone" → check visibility). It will hold
   client-derived data during development and must never be public.
2. Install **GitHub Desktop** (desktop.github.com) if you don't have it, sign in, then:
   File → Clone Repository → pick `Kaizen74/AI-Org-Advisory-Workbench` → choose where to save it
   → Clone. You now have a local folder connected to GitHub.
3. Put these FIVE files into that cloned folder:
   - BUILD_SPEC_ADVISORY_WORKBENCH.md (v1.2)
   - PRD_AI_Transformation_Advisory_Workbench.md (v1.2)
   - taxonomy_seed.starter.json (your WI starter seed — Claude Code will place it under
     backend/app/resources/taxonomies/ in Phase 2)
   - WORKFORCE_INTELLIGENCE_ARCHITECTURE.md (Claude Code reads it in Phase 0 and moves it to /docs)
   - This prompts file (optional, for your own reference).
4. Copy your ENTIRE existing v1 app folder (claude-org-design-analyzer) into the cloned folder
   and rename that copy `legacy`. The spec tells Claude Code to port the proven parts (metrics
   engine, CSV parser, archetypes, test fixtures) from there instead of rebuilding them — and to
   set up .gitignore rules BEFORE the first push so no database or client files ever reach GitHub.
5. Open Claude Code in the cloned folder.
6. Paste PROMPT 1. After Phase 0, review its report, then tell it to proceed to Phase 1.
7. Every new session after that: paste PROMPT 2.
8. Your extra 30-second check from now on: open the repo on github.com — the latest commit
   timestamp should match your last session. If it doesn't, ask Claude Code to push.

## How to know things are healthy (your 30-second check, any time)

- Open `.checkpoints/LATEST.md` — it should always tell you, in plain language, the current
  phase, what was last finished, what is half-done, and the exact next step.
- "Test status" in that file should say PASS. If it says FAIL, the note will say why and the
  next session's first job is to fix it.
- `PROGRESS.md` should have a dated entry for every session — if a session happened but no entry
  exists, ask Claude Code to reconcile before doing anything else.
