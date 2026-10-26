#!/bin/bash
# start.sh
# Container entrypoint that starts both the FastAPI HTTP server and the MCP
# SSE server concurrently. Both processes are kept alive by wait; if either
# exits unexpectedly the script propagates the failure so Docker can restart
# the container according to its restart policy.

set -euo pipefail

echo "[start.sh] Starting RAG backend services..."

# ── FastAPI / Uvicorn (port 8000) ─────────────────────────────────────────────
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --log-level info \
  --no-access-log &
UVICORN_PID=$!
echo "[start.sh] uvicorn started (PID $UVICORN_PID)"

# ── MCP SSE Server (port 8001) ────────────────────────────────────────────────
python -m app.mcp_server.server &
MCP_PID=$!
echo "[start.sh] MCP server started (PID $MCP_PID)"

# ── Wait for either process to exit ──────────────────────────────────────────
wait_any() {
  while true; do
    if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
      echo "[start.sh] uvicorn exited unexpectedly -- killing MCP server"
      kill "$MCP_PID" 2>/dev/null || true
      wait "$MCP_PID" 2>/dev/null || true
      exit 1
    fi
    if ! kill -0 "$MCP_PID" 2>/dev/null; then
      echo "[start.sh] MCP server exited unexpectedly -- killing uvicorn"
      kill "$UVICORN_PID" 2>/dev/null || true
      wait "$UVICORN_PID" 2>/dev/null || true
      exit 1
    fi
    sleep 5
  done
}

trap 'echo "[start.sh] Received shutdown signal"; kill $UVICORN_PID $MCP_PID 2>/dev/null || true; wait' SIGTERM SIGINT

wait_any
