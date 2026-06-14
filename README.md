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
- _Workflow Mapper_ — map tasks onto end-to-end processes/value streams and score AI opportunity
  (L0–L3) per process. ✅ _(Phase 5)_
- _Transition Planner_ — for a scenario, classify how each role is affected (unchanged/augmented/
  transformed/displaced/new), suggest SkillsFuture reskilling pathways, and export a transition
  register. ✅ _(Phase 5)_
- _Deliverables_ — one-click branded PowerPoint/Word/Excel exports (diagnostic, scenario
  comparison, AI roadmap, TOM, metrics, transition register), each with an auto-generated provenance
  page; unreviewed AI content is automatically blocked. ✅ _(Phase 6 — modern-minimalist template)_
- _Settings_ — enter your Anthropic API key in the app (no editing files), switch to a **local LLM**
  on your computer for when online models are down, and set a **brand logo + colour palette** that
  the deck template adopts (SATS preconfigured). ✅ _(pre-P7)_
- _Security_ — per-engagement anonymization (pseudonyms; no real names in exports), real-name purge
  + full purge (PDPA), and an audit trail; Postgres-ready for cloud deploy. ✅ _(Phase 7)_

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

Phase-1 screens (Engagements, Diagnostics) need **no API key**. For the AI features, open the
**Settings** tab in the app and paste your **Anthropic API key** (create one at
<https://console.anthropic.com>) — it is stored on the server, never shown back in full, and you
never edit any file. If online AI models are ever disrupted, switch the provider in Settings to
**Local LLM** and point it at a local server on your computer (e.g. Ollama at
`http://localhost:11434/v1`). Settings is also where you set a **brand logo + colour palette** for
the generated decks (choose the “Brand” template on the Deliverables tab).

---

## 4. Deploy to the cloud (Vercel + Railway)

You host the **backend** (the engine) on **Railway** and the **frontend** (the browser view) on
**Vercel**. Both connect to this GitHub repo, so pushing to `main` redeploys automatically. A
"**environment variable**" is a setting you type into the hosting website (not into a file) — like
your API key or database address.

> **Note:** these steps were written from the services' standard flow. The exact button wording can
> change as Vercel/Railway update their sites; the names below are what to look for. Do this once.

### 4a. Backend on Railway
1. Go to <https://railway.app> → sign in with GitHub.
2. Click **New Project** → **Deploy from GitHub repo** → pick
   `Kaizen74/AI-Org-Advisory-Workbench` → when asked for the root/subdirectory, choose **`backend`**.
3. Add a database: in the project, click **New** → **Database** → **Add PostgreSQL**. Railway creates
   it and a `DATABASE_URL` variable.
4. Open your service → **Variables** and set:
   - `DATABASE_URL` — change the prefix Railway gives you from `postgresql://` to
     **`postgresql+asyncpg://`** (everything else stays the same).
   - `ANON_SALT` — any long random string (e.g. mash the keyboard for 30+ characters).
   - `CORS_ORIGINS` — leave blank for now; you'll paste the Vercel URL here in step 4c.
   - _(You do NOT need to set the Anthropic key here — you'll enter it in the app's Settings page.)_
5. Set the **Start Command** (Settings → Deploy) to:
   `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   (a `Procfile` in `backend/` already contains this, so Railway usually picks it up automatically).
6. Click **Deploy**. When it's live, copy the public URL (looks like
   `https://your-app.up.railway.app`) — this is your **backend URL**.

### 4b. Frontend on Vercel
1. Go to <https://vercel.com> → sign in with GitHub → **Add New… → Project** → import
   `Kaizen74/AI-Org-Advisory-Workbench`.
2. Set **Root Directory** to **`frontend`**. Vercel auto-detects Vite (Build: `npm run build`,
   Output: `dist`).
3. Under **Environment Variables** add `VITE_API_BASE_URL` = your **backend URL** from step 4a-6
   (e.g. `https://your-app.up.railway.app`, no trailing slash).
4. Click **Deploy**. When done, copy the frontend URL (looks like
   `https://your-app.vercel.app`) — this is the link you open to use the app.

### 4c. Connect the two
1. Back in Railway → your service → **Variables** → set `CORS_ORIGINS` to your Vercel URL
   (e.g. `https://your-app.vercel.app`) and redeploy.
2. Open the Vercel URL, go to **Settings** in the app, paste your **Anthropic API key**, and you're
   live.

### 4d. Redeploying after changes
Just push to `main` (or merge a branch into `main`). Railway and Vercel both rebuild automatically.

---

## 5. Updating the app

- **On your computer:** in GitHub Desktop open the repo → **Fetch origin** → **Pull**, then restart
  the two terminals from Section 3 (run `pip install -r requirements.txt`, `alembic upgrade head`,
  and `npm install` again if you were told dependencies changed).
- **In the cloud:** nothing to do — pushing to `main` redeploys Railway + Vercel automatically.

---

## 6. If something goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| `command not found: python3` / `pip` | Python not installed or not on PATH | Re-install Python 3.11+ (Section 2); on Windows tick "Add to PATH" during install |
| `command not found: node` / `npm` | Node.js not installed | Install Node LTS (Section 2), then reopen the terminal |
| Backend won't start: `address already in use` / port 8000 busy | Another program (or an old run) holds the port | Close the other window, or run `uvicorn app.main:app --reload --port 8001` |
| App opens but every action errors / "Failed to fetch" | Backend not running, or frontend pointing at the wrong API | Make sure Terminal 1 shows `Uvicorn running`; in the cloud, check `VITE_API_BASE_URL` on Vercel matches the Railway URL |
| AI buttons say "Anthropic API key not configured" | No key set (or wrong provider) | Open **Settings** → paste your key, or switch provider to **Local LLM** |
| Local LLM doesn't respond | Local server not running / wrong URL | Start Ollama/LM Studio; set the right URL in Settings (`http://localhost:11434/v1` for Ollama, `http://localhost:1234/v1` for LM Studio) |
| `database is locked` (SQLite) | Two processes writing at once | Stop extra backend windows; for production use Postgres (Section 4) |
| Blank white page in browser | Frontend build/old cache | Hard-refresh (Ctrl/Cmd+Shift+R); locally re-run `npm run dev` |
| Railway build fails | Wrong root dir or missing start command | Root dir must be `backend`; set the Start Command in step 4a-5 |
| Vercel shows a 404 / API calls fail | Root dir or env var wrong | Root dir must be `frontend`; set `VITE_API_BASE_URL` (step 4b-3) |
| CORS error in browser console | Backend not allowing the Vercel origin | Set `CORS_ORIGINS` on Railway to your Vercel URL (step 4c) |

If you're stuck, copy the red error text and paste it to Claude Code with a note of what you did.

---

## 7. Data & privacy notes

- This GitHub repository is **private** — it may hold client-derived data during development and
  must never be made public.
- **Client data is never committed** to the repo. The `.gitignore` file blocks databases, uploaded
  CSVs, secret keys (`.env`), uploaded logos, and generated deliverables from ever reaching GitHub.
  The only data files in the repo are the synthetic PAX sample, the taxonomy seed, and the SATS
  brand logo.
- **Anonymization mode** (tick "anonymized" when creating an engagement): real names are replaced
  with stable pseudonyms (e.g. `EMP-1A2B3C4D`) at upload, and **no real name appears in any export**
  (verified by an automated test). Real names live only inside the app's database.
- **Purge real names** (PDPA "right to deletion" of personal data): `DELETE` the engagement's
  `/real-names` — it scrubs the names but keeps the (pseudonymized) analysis.
- **Purge an engagement** entirely: deletes all of its data on demand.
- **Audit trail:** uploads, AI calls, validations, exports, and purges are logged per engagement
  (viewable via the audit endpoint).
- **Your API key** is stored in the app's database (never in the repo) and is shown back only
  masked.

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
