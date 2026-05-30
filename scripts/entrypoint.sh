#!/usr/bin/env bash
# Boots the FastAPI backend and Next.js frontend inside one Fly machine.
# If either dies, we exit so Fly restarts the machine.
set -euo pipefail

mkdir -p "$(dirname "${LYRICSTATS_DB:-/data/lyricstats.db}")"

cleanup() {
  echo "[entrypoint] shutting down…"
  kill 0 2>/dev/null || true
}
trap cleanup TERM INT

echo "[entrypoint] starting FastAPI on 127.0.0.1:8000"
uvicorn backend.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --log-level info &
API_PID=$!

echo "[entrypoint] starting Next.js on 0.0.0.0:${PORT:-3000}"
(
  cd web
  exec node_modules/next/dist/bin/next start \
    --hostname 0.0.0.0 \
    --port "${PORT:-3000}"
) &
WEB_PID=$!

# Wait for whichever exits first, then exit so the machine restarts.
wait -n "$API_PID" "$WEB_PID"
EXIT_CODE=$?
echo "[entrypoint] a process exited with $EXIT_CODE — tearing down."
exit "$EXIT_CODE"
