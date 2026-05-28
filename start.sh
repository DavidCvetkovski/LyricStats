#!/usr/bin/env bash
# One-command launcher: starts FastAPI backend + Next.js frontend.
set -euo pipefail
cd "$(dirname "$0")"

# ── prerequisites ──────────────────────────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install from https://docs.astral.sh/uv/" >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "npm is not installed. Install Node.js from https://nodejs.org/" >&2
  exit 1
fi
if [ ! -f .env ]; then
  echo "⚠️  .env not found — copy .env.example to .env and add your GENIUS_TOKEN" >&2
  exit 1
fi

# ── python deps ────────────────────────────────────────────────────────────
if [ ! -d .venv ] || [ pyproject.toml -nt .venv ]; then
  echo "→ syncing python deps…"
  uv sync --extra dev
fi

# ── js deps ────────────────────────────────────────────────────────────────
if [ ! -d web/node_modules ] || [ web/package.json -nt web/node_modules ]; then
  echo "→ installing js deps…"
  (cd web && npm install --no-progress --no-audit --no-fund)
fi

# ── launch both, kill both on Ctrl-C ───────────────────────────────────────
cleanup() {
  echo
  echo "→ shutting down…"
  [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true
  [ -n "${WEB_PID:-}" ] && kill "$WEB_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "→ starting FastAPI on http://localhost:8000"
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000 --log-level warning &
API_PID=$!

echo "→ starting Next.js on http://localhost:3000"
(cd web && npm run dev -- --port 3000) &
WEB_PID=$!

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  LyricStats is live at  http://localhost:3000"
echo "  API at                 http://localhost:8000/health"
echo "  Press Ctrl-C to stop both."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

wait
