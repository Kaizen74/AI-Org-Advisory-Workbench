# OrgAI Advisory Workbench

> **Status:** All build phases complete (P0–P7) — the app runs locally and is ready for its first
> cloud deployment (Section 4). This README is written for a **non-technical owner**: if a word
> looks like jargon, it is explained the first time it appears.

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
- _Workflow Mapper_ — the heart of the app: a visual drag-and-drop board that maps tasks onto
  end-to-end processes, scored on the **Human Agency Scale (H0–H5)** from Stanford's WORKBank
  research. Three views: **Flow** (the board), **Landscape** (capability × worker desire, with the
  four WORKBank zones), and **Roll-up** (an org chart with AI opportunity aggregated up the
  reporting lines to each department head; click a role to see its tasks and where they're mapped).
  Exports the finalized workflow as CSV or a branded PowerPoint. ✅ _(Phase 5, expanded)_
- _Scenario Studio_ & _Transition Planner_ — future-state design moves and role-impact/reskilling
  registers. ✅ _(Built and tested; currently hidden behind a switch — `SHOW_SIMULATION` in
  `frontend/src/config.ts` — to keep the app focused on role → task → AI-potential. Flip it to
  `true` to restore the two tabs.)_
- _Deliverables_ — one-click branded PowerPoint/Word/Excel exports (diagnostic, scenario
  comparison, AI roadmap, TOM, metrics, transition register), each with an auto-generated provenance
  page; unreviewed AI content is automatically blocked. ✅ _(Phase 6 — modern-minimalist template)_
- _Settings_ — enter your Anthropic API key in the app (no editing files), switch to a **local LLM**
  on your computer for when online models are down, and set a **brand logo + colour palette** that
  the deck template adopts (SATS preconfigured). ✅ _(pre-P7)_
- _Security_ — **private sign-in** (email + passcode allowlist; the app is never public),
  per-engagement anonymization (pseudonyms; no real names in exports), real-name purge + full purge
  (PDPA), and an audit trail; Postgres-ready for cloud deploy. ✅ _(Phase 7)_

---

## 1b. The research behind the scores (methodology anchors)

The app's AI-potential language is deliberately anchored to published research, so what a client
sees in a deliverable can be traced to a credible source (last calibrated **July 2026**):

- **Human Agency Scale (H0–H5)** and the **WORKBank** dataset come from Stanford's *"Future of Work
  with AI Agents"* study ([arXiv:2506.06576](https://arxiv.org/abs/2506.06576); data:
  [SALT-NLP/WORKBank](https://github.com/SALT-NLP/workbank)) — 1,500 workers and AI experts rating
  844 tasks across 104 occupations. H1 = an AI agent can handle the task entirely; H3 = equal
  human–AI partnership; H5 = human involvement essential. **H0 is this app's own extension** for
  tasks with no software-agent overlay (physical work → a robotics lever instead).
- **The four Landscape quadrants** (Green Light / Red Light / R&D Opportunity / Low Priority) are
  the paper's zones, defined by **capability × worker desire**. Note the counter-intuitive one:
  *Red Light* means AI *can* do the task but workers *don't want it automated* — deploy there with
  caution and change management, not enthusiasm. The study found workers' top concerns are lack of
  trust (45%), fear of replacement (23%), and loss of human touch (16%).
- **Automation vs augmentation:** H1–H2 tasks favour automation strategies; H3–H4 favour
  augmentation (human–AI collaboration). H3 "equal partnership" is the most worker-desired level in
  roughly 45% of occupations — and real-world usage agrees: the
  [Anthropic Economic Index](https://www.anthropic.com/news/the-anthropic-economic-index) measures
  a near-even split (augmentation ~52% / automation ~45% of AI conversations as of 2026). So the
  augmentation count in the Workflow Mapper is an opportunity class in its own right.
- **The go/no-go zone on each task card** (GREEN_LIGHT / RED_LIGHT / ROBOTICS) is this app's own
  derived signal — capability × H-band — kept deliberately separate from the desire-based WORKBank
  zones above (desire data is often not yet captured for a client; the Landscape shows it once it is).
- All WORKBank-derived values remain **illustrative until verified for the client** — the app
  caveats them automatically and blocks unreviewed AI content from deliverables.

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
cp .env.example .env                  # one time — then open .env and set ACCESS_USERS (your login)
alembic upgrade head                  # creates the local database file (one time per machine)
uvicorn app.main:app --reload         # starts the engine
```

The app is private, so you sign in with an email + passcode. In `backend/.env`, set for example
`ACCESS_USERS=you@example.com:my-passcode` — that's the login you'll type on the sign-in screen.
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
**Local LLM** (see Section 3b). Settings is also where you set a **brand logo + colour palette** for
the generated decks (choose the “Brand” template on the Deliverables tab).

---

## 3b. Using a local LLM (LM Studio / Qwen) — optional

When the online Claude models are disrupted (or you simply prefer to keep everything on your own
machine), you can run the AI features against a **local model** such as **Qwen** served by
**LM Studio**. Nothing in the app changes except a few settings — flip back to Anthropic any time.

**One-time setup in LM Studio:**
1. Install **LM Studio** (<https://lmstudio.ai>) and, in its **Search/Discover** tab, download a
   model (e.g. a **Qwen** instruct model that fits your laptop's memory).
2. Open the **Developer / Local Server** tab → **Load** the model → **Start Server**. LM Studio will
   show a base URL, normally **`http://localhost:1234/v1`**, and the **model identifier** of the
   loaded model (copy it exactly).

**In the Workbench (Settings → AI model provider):**
1. Set **Provider** to **Local LLM**.
2. Set **Local base URL** to `http://localhost:1234/v1` (LM Studio's address).
3. Set **Local model** to the model id LM Studio showed (e.g. `qwen3-27b-instruct`).
4. Click **Test connection** — you should see “Connection OK (local)”. Click **Save**.

From now on, extraction, benchmarking, AI-opportunity, and the deck’s priority text all run on your
local model. (Local models are slower and a little less precise than the frontier Claude models —
keep the validation queue in mind before exporting.)

> **Important — where the backend runs:** the *backend* makes the model call, so LM Studio must be
> reachable from wherever the backend runs.
> - **All on your laptop** (local backend from Section 3 **+** LM Studio): works out of the box —
>   this is the intended “offline / disruption” setup.
> - **Backend in the cloud (Railway) + LM Studio on your laptop:** the cloud server cannot see
>   `localhost` on your laptop. Either run the backend locally when you want the local model, or
>   expose LM Studio over the internet with a tunnel (e.g. ngrok/Cloudflare Tunnel) and put that
>   public URL in **Local base URL**. For everyday cloud use, keep the provider on **Anthropic**.

---

## 3c. Working with Capability Compass — optional

This app can read the hand-off file that **Capability Compass** writes at the end of Stage 1, and
write its findings back in one agreed shape. **None of this is required** — skip it and the app
works on its own exactly as before.

**Import (Engagements tab):**

1. Open **Engagements**. Scroll to **Import from Capability Compass (optional)**.
2. Click **Choose hand-off file** and pick `<key>_compass_handoff.json` (for example
   `meridian_compass_handoff.json`).
3. Read the preview. It lists what will be created or changed, any warnings, and one row per role.
   **Nothing is saved yet.**
4. In the **Job title in the org file** column, check each match. "Near-match — please choose" is
   never applied on its own: pick a title or leave it unmatched.
5. Click **Confirm import**. To change a match later, use the **Capability Compass roles** panel
   on the same page.

Tip: upload the org CSV first, then import — the roles can then be matched in the same step. If
you import first, upload the CSV and click the "Same title found in the org file" links.

**What you then see:**

| Where | What changes |
|---|---|
| Engagements | The engagement shows its key (e.g. `MERIDIAN`). |
| Task Intelligence | A **Compass roles** panel: roles in Compass order, with route badge, positions and tasks. Roles with status *absent* are listed as "no one in the seat" and are not analysed. |
| Workflow Mapper | Tasks of Compass roles come first, with a badge such as `RL-009 · specialist`. A **⚠ tacit-knowledge warning** appears when a `specialist` or `dual` role's task is proposed at H1 or H2. Each task shows its `T-nnn` code. Click a step to enter its **Process Map Studio step ID** (`S-04`). |
| Validation Queue | A new **Evidence grade** column (see below) and the same warning. |
| Deliverables | Two new buttons: **Findings return for Compass (.json)** and **Findings return — readable text (.txt)**. |

**Evidence grade (the same three words in all four apps):**

| Grade | When |
|---|---|
| **Hypothesis** | Unreviewed AI output, or anything below 0.70 confidence. Never drives a decision on its own. |
| **Indicated** | You approved (or edited) it in the Validation Queue. |
| **Confirmed** | You raised it yourself: tick **Show reviewed** in the Validation Queue, then click **raise to Confirmed**. The app never sets this on its own. |

**The return file** contains three kinds of finding: task dispositions (`T-nnn`), role impact
(`RL-nnn`) and capacity (FTE freed — always an *estimate*, always graded Hypothesis). Unreviewed AI
content is left out, exactly as in every other deliverable. It contains no names of people, no API
key and no document text. Upload the `.txt` version to Capability Compass as a document.

## 4. Deploy to the cloud (Vercel + Railway)

You host the **backend** (the engine) on **Railway** and the **frontend** (the browser view) on
**Vercel**. Both connect to this GitHub repo, so pushing to `main` redeploys automatically. A
"**environment variable**" is a setting you type into the hosting website (not into a file) — like
your API key or database address.

> **The app is private.** It is hosted on the internet but **locked behind a sign-in screen** — only
> people you put on the allowlist (email + passcode) can get in, so the public never sees the SATS
> look-and-feel. The public sees only a neutral "please sign in" page. You set the first owner
> account with the `ACCESS_USERS` variable below, then add/remove others inside the app
> (**Settings → Access control**).

> **Note:** these steps were checked against the services' current documentation (July 2026). The
> exact button wording can still change as Vercel/Railway update their sites; the names below are
> what to look for. Do this once — total time is about 30–45 minutes.

**What you need before starting (the pre-flight list):**

- [ ] A **GitHub account** that can see this repository (you have this — it's your repo).
- [ ] A **Railway account** (<https://railway.app>) — sign up with the "Login with GitHub" button.
- [ ] A **Vercel account** (<https://vercel.com>) — also sign up with GitHub.
- [ ] Your **Anthropic API key** (from <https://console.anthropic.com>) — you'll paste it into the
      app's Settings page at the very end, not into any hosting site.
- [ ] Two long random strings for `ANON_SALT` and `AUTH_SECRET` (open a password manager and
      generate two 40-character passwords — that's all these are).
- [ ] Decide your first login: an email + a strong passcode (this becomes `ACCESS_USERS`).
- [ ] The code must be on the **`main` branch** (or point Railway/Vercel at your working branch —
      both services let you pick the branch under their settings).

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
   - `AUTH_SECRET` — another long random string (this signs the sign-in tokens).
   - `ACCESS_USERS` — your first owner login as `email:passcode` (e.g.
     `you@company.com:a-strong-passcode`). You can add more people later in the app. **This is what
     keeps the app private** — without a matching login, no one gets past the sign-in screen.
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
2. Open the Vercel URL — you'll see the **sign-in screen**. Log in with the `ACCESS_USERS` email +
   passcode you set in step 4a-4. Then go to **Settings**, paste your **Anthropic API key**, and (in
   **Settings → Access control**) add any other people who should have access. You're live and private.

### 4d. Verify it worked (5-minute checklist)
1. Open **`https://your-app.up.railway.app/health`** in a browser — you should see
   `{"status":"ok"}`. (This is the only page that works without signing in.)
2. Open your **Vercel URL** — you should see the neutral **sign-in screen** (no SATS branding
   visible before login — that's by design).
3. Sign in with your `ACCESS_USERS` email + passcode.
4. Go to **Settings** and check the **AI model** fields show `claude-sonnet-5` (extraction) and
   `claude-opus-4-8` (synthesis). Paste your **Anthropic API key** and click **Test connection** —
   you want "Connection OK".
5. Go to **Engagements** → create a client + engagement → upload an org CSV → click **Diagnose →**.
   If the metric tiles appear, the whole chain (browser → Vercel → Railway → database) works.
6. Run the pipeline on the **Task Intelligence** tab, review items in the **Validation Queue**, and
   open the **Workflow Mapper** — you're fully live.

### 4e. Redeploying after changes
Just push to `main` (or merge a branch into `main`). Railway and Vercel both rebuild automatically —
there is nothing to click. Give them 2–3 minutes, then hard-refresh your browser
(Ctrl/Cmd+Shift+R).

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
| Can't sign in / "Invalid email or passcode" | Not on the allowlist, or typo | Use an `ACCESS_USERS` login; an owner can add you in Settings → Access control |
| Locked out (no owner) | `ACCESS_USERS` was never set | Set `ACCESS_USERS` on Railway and redeploy — it seeds an owner if the list is empty |

If you're stuck, copy the red error text and paste it to Claude Code with a note of what you did.

---

## 7. Data & privacy notes

- The deployed app is **private**: it sits behind a sign-in screen and only allowlisted users
  (email + passcode) can enter — the public never sees the SATS brand or any content. Owners manage
  the allowlist in **Settings → Access control**; passcodes are stored only as salted hashes.
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
