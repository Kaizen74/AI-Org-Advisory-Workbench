# OrgAI Advisory Workbench

> **Status:** Early build (Phase 0 — foundations). This README grows as features ship. It is
> written for a **non-technical owner**: if a word looks like jargon, it is explained the first
> time it appears.

---

## 1. What this app is

The OrgAI Advisory Workbench is a tool that takes a company's HR/org data and helps turn it into a
validated, client-ready organization design and AI-transformation plan. It is for an AI
transformation advisor (Eric) running client engagements — diagnosing the current organization,
designing future-state options, checking every AI recommendation with a human before it appears in
a deliverable, and producing the slides/documents at the end. **Modules (each line appears here as
it ships):**

- _Engagement Hub_ — manage clients, engagements, and uploaded org-CSV data sets. ✅ _(Phase 1)_
- _Diagnostics_ — org-structure metrics (employees, managers, span, layers, cost, manager ratio),
  the 7-archetype reference, and a Five-Activator pre-screen. ✅ _(Phase 1)_
- _Task Intelligence_ — turns each role's work activities into tasks, benchmarks them against
  skills taxonomies, and scores AI-automation opportunity (L0–L3) with full provenance and caveats.
  ✅ _(Phase 2; the AI parts need an Anthropic API key.)_
- _Validation Queue_ — review/approve/reject the AI's mappings in bulk (filtered by confidence);
  approvals teach the system, and a desire-pulse instrument captures local automation preferences
  alongside (never overwriting) the US data. ✅ _(Phase 3)_
- _Scenario Studio_ — design future-state org options as a list of "moves" (merge/split/reparent/
  add/delete/regrade), see live deltas vs the baseline, and compare scenarios side-by-side; present
  to lock, fork to keep editing. ✅ _(Phase 4)_
- _(later phases: Workflow Mapper, Transition Planner, Deliverables, Settings.)_

---

## 2. Before you begin (one-time installs)

A "**terminal**" (also called a "command line") is a window where you type commands instead of
clicking buttons. You'll use it to start the app. You install three things once:

| Tool | What it is | Where to get it | How to check it worked |
|---|---|---|---|
| **Git** (or **GitHub Desktop**) | Software that copies the project from GitHub to your computer and sends changes back. A "**repository**" (or "repo") is just the project folder that Git tracks. | <https://desktop.github.com> (easiest) or <https://git-scm.com> | In a terminal type `git --version` and press Enter. A good answer looks like `git version 2.x.x`. |
| **Python 3.11+** | The language the app's "**backend**" (the engine that does the calculations) is written in. | <https://www.python.org/downloads/> | Type `python3 --version`. A good answer looks like `Python 3.11.x` (or higher). |
| **Node.js LTS** | The tool that runs the app's "**frontend**" (the part you see in the web browser). "LTS" = the stable long-term-support version. | <https://nodejs.org> (click the **LTS** button) | Type `node --version`. A good answer looks like `v20.x.x` or `v22.x.x`. |

> _Detailed click-by-click install steps with screenshots will be finalized in Phase 7._

---

## 3. Run the app on your own computer

You open **two terminal windows** — one for the **backend** (the calculation engine) and one for
the **frontend** (the browser view) — leave both running, then open the app in your browser.

**Terminal 1 — start the backend** (a "terminal" is the text window from Section 2):

```bash
cd backend
python3 -m venv .venv                 # makes a private Python sandbox (one time)
source .venv/bin/activate             # turns the sandbox on (Windows: .venv\Scripts\activate)
pip install -r requirements.txt       # installs the engine's parts (one time)
alembic upgrade head                  # creates the local database file (one time per machine)
uvicorn app.main:app --reload         # starts the engine
```

Success looks like `Uvicorn running on http://127.0.0.1:8000` — **leave this window open.**

**Terminal 2 — start the frontend** (open a second terminal window):

```bash
cd frontend
npm install                           # installs the browser-view parts (one time)
npm run dev                           # starts the view
```

Success looks like `Local: http://localhost:5173/` — **leave this window open** and click that link
(or paste it into your browser). You'll see the Workbench. Go to **Engagements**, add a client and
an engagement, upload an org CSV, then click **Diagnose →** to compute the metrics.

**One-command health check** (proves nothing is broken — runs the self-tests and a build):

```bash
bash scripts/gate.sh
```

Phase-1 screens (Engagements, Diagnostics) need **no API key**. The **Anthropic API key** (the
password-like string that lets the app use Claude AI) is only needed from Phase 2 on; you'll create
one at <https://console.anthropic.com> and paste it into the Settings screen when it ships.

---

## 4. Deploy to the cloud (Vercel + Railway)

> _Click-by-click instructions with the actual button names will be captured during the Phase 7
> deployment and finalized here._ In short: connect this GitHub repo to **Vercel** (hosts the
> frontend) and **Railway** (hosts the backend), set the environment variables (your API key and
> model settings — explained here when we get there), and deploy. After that, pushing changes to
> the `main` branch redeploys automatically.

---

## 5. Updating the app

> _Finalized in Phase 7._ In GitHub Desktop: open the repo → **Fetch origin** → **Pull** to get the
> latest version, then restart the two terminals from Section 3.

---

## 6. If something goes wrong

> _A full troubleshooting table (port already in use, missing API key, `pip`/`npm` not found,
> database locked, blank page, Railway build failure, etc.) is filled in as those situations become
> reachable in later phases._ For now, if `bash scripts/gate.sh` fails, copy the red error text and
> paste it to Claude Code with a note of what you did.

---

## 7. Data & privacy notes

- This GitHub repository is **private** — it may hold client-derived data during development and
  must never be made public.
- **Client data is never committed** to the repo. The `.gitignore` file blocks databases, uploaded
  CSVs, secret keys (`.env`), and generated deliverables from ever being sent to GitHub. The only
  data files allowed in the repo are the synthetic PAX sample and the taxonomy seed.
- **Anonymization mode** (per engagement) replaces real names with stable pseudonyms so exports
  carry no real names. _(Ships in Phase 7.)_
- **Purging an engagement** deletes all of its data on demand (a PDPA "right to deletion" feature).
  _(Ships in Phase 7.)_

---

## 8. For developers / Claude Code

The build is governed by these files — read them in this order:

- **[`CLAUDE.md`](CLAUDE.md)** — the mandatory operating protocol (auto-loaded each session).
- **[`BUILD_SPEC_ADVISORY_WORKBENCH.md`](BUILD_SPEC_ADVISORY_WORKBENCH.md)** — the executable build
  spec (Part A protocol + Part B requirements).
- **[`PRD_AI_Transformation_Advisory_Workbench.md`](PRD_AI_Transformation_Advisory_Workbench.md)** —
  the product requirements and rationale.
- **[`.checkpoints/LATEST.md`](.checkpoints/LATEST.md)** — the current build state: what was last
  done, what's in flight, and the exact next step.
