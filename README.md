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

- _Engagement Hub_ — manage clients, engagements and uploaded data sets. _(coming in Phase 1)_
- _Diagnostics_ — org structure metrics (spans, layers, cost, manager ratio). _(coming in Phase 1)_
- _(later phases: Task Intelligence, Validation Queue, Scenario Studio, Workflow Mapper, Transition
  Planner, Deliverables, Settings.)_

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

> _Full numbered, copy-paste steps land when Phase 1 ships the first usable screens._ The shape is:
> you open **two terminal windows** — one for the **backend** (the calculation engine) and one for
> the **frontend** (the browser view) — leave both running, then open the app in your browser.

Quick check that the foundations work (you can run this today):

```bash
bash scripts/gate.sh
```

This runs the app's automated self-tests and builds the frontend. Success looks like a final line
saying the gate passed. _(The "gate" is a single safety check that proves nothing is broken.)_

You'll enter your **Anthropic API key** (the password-like string that lets the app use Claude AI)
in the app's Settings screen once it ships. You can create a key at
<https://console.anthropic.com>. _Where to paste it will be documented here in Phase 1._

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
