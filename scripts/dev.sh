#!/usr/bin/env bash
# Local development: FastAPI with auto-reload on :8000 and the Vite dev server on :5173.
# Needs Postgres with pgvector reachable at DATABASE_URL (default postgresql://upsc:upsc@localhost:5432/upsc)
# and backend/.venv (see README → Develop). Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."

(cd backend && exec .venv/bin/uvicorn app.main:app --reload --port 8000) &
API=$!
(cd frontend && exec npm run dev -- --port 5173) &
WEB=$!
trap 'kill $API $WEB 2>/dev/null' EXIT INT TERM

echo "API  http://localhost:8000/docs"
echo "App  http://localhost:5173"
wait
