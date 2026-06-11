#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# REGRESSION GATE (Build Spec A3, Rule 3)
# One command, run at: session start, after every phase, after every bug fix,
# and at session end. Passes only if the backend suite AND the frontend build
# are both green. Sets up a Python venv and installs deps on first run.
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "════════════════════════════════════════════════════════════════════"
echo "  OrgAI Advisory Workbench — regression gate"
echo "════════════════════════════════════════════════════════════════════"

# ── Backend: venv + deps + pytest ───────────────────────────────────────────
echo ""
echo "── [1/2] Backend: pytest ───────────────────────────────────────────"
cd "$ROOT/backend"

if [ ! -d ".venv" ]; then
  echo "Creating Python virtual environment (.venv)…"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# Install deps only when requirements.txt is newer than the install marker.
if [ ! -f ".venv/.deps-installed" ] || [ requirements.txt -nt ".venv/.deps-installed" ]; then
  echo "Installing backend dependencies…"
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
  touch ".venv/.deps-installed"
fi

PYTHONPATH="$ROOT/backend" pytest tests/ -v

# ── Frontend: npm install + build (zero TypeScript errors) ───────────────────
echo ""
echo "── [2/2] Frontend: npm run build ───────────────────────────────────"
cd "$ROOT/frontend"

if [ ! -d "node_modules" ]; then
  echo "Installing frontend dependencies…"
  npm install --silent
fi

npm run build

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "  ✅ GATE PASSED — backend tests green, frontend builds clean."
echo "════════════════════════════════════════════════════════════════════"
