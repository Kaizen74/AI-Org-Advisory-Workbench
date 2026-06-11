.PHONY: gate backend frontend

# One-command regression gate (Build Spec A3, Rule 3).
gate:
	bash scripts/gate.sh

# Run the backend dev server (after the gate has set up .venv).
backend:
	cd backend && . .venv/bin/activate && PYTHONPATH=$(CURDIR)/backend uvicorn app.main:app --reload

# Run the frontend dev server.
frontend:
	cd frontend && npm run dev
