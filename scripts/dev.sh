#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -f .env ] || cp .env.example .env
source .venv/bin/activate
trap 'kill 0' EXIT
(cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) &
(cd frontend && npm run dev) &
wait
