#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env — run ./scripts/setup.sh first" >&2
  exit 1
fi
if [[ ! -d .venv ]]; then
  echo "Missing .venv — run ./scripts/setup.sh first" >&2
  exit 1
fi
# shellcheck source=/dev/null
source .venv/bin/activate
mkdir -p logs
exec uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --env-file .env
