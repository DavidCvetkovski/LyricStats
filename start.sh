#!/usr/bin/env bash
# One-command launcher: installs (first time only) and runs the app.
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install it from https://docs.astral.sh/uv/" >&2
  exit 1
fi

# Sync deps if the venv is missing or pyproject changed
if [ ! -d .venv ] || [ pyproject.toml -nt .venv ]; then
  echo "→ installing dependencies…"
  uv sync --extra dev
fi

if [ ! -f .env ]; then
  echo "⚠️  .env not found — copy .env.example to .env and add your GENIUS_TOKEN" >&2
  exit 1
fi

echo "→ starting LyricStats at http://localhost:8501"
exec uv run streamlit run streamlit_app.py
