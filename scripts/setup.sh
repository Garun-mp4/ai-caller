#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -f .env ] || cp .env.example .env
python3 -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ required"'
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r backend/requirements.txt
(cd frontend && npm install)
(cd backend && alembic upgrade head)
python scripts/check_env.py
echo "Setup complete. Run ./scripts/dev.sh"
