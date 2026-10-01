#!/usr/bin/env bash
# Starts the API (with the in-process MCP gateway), dashboard, and demo
# fixture servers in the foreground.
# Assumes Postgres is already running (e.g. via Docker Desktop).
# Ctrl+C stops everything this script started.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Checking Postgres..."
if ! docker compose ps --status running 2>/dev/null | grep -q postgres; then
  echo "    WARNING: postgres container not detected as running (check Docker Desktop)." >&2
fi
source venv/bin/activate
export PYTHONPATH="$REPO_ROOT"

PIDS=()

cleanup() {
  echo ""
  echo "==> Stopping all processes started by this script..."
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null
  done
  wait 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "==> Starting API (with in-process MCP gateway) on :8001"
uvicorn app.main:app --reload --port 8001 --host 0.0.0.0 &
PIDS+=("$!")

echo "==> Starting dashboard on :3000"
(cd frontend && npm run dev) &
PIDS+=("$!")

echo "==> Starting demo fixture servers on :8901 :8902 :8903"
python3 -m scripts.demos.fixture_servers start &
PIDS+=("$!")

echo ""
echo "==> All processes running (output interleaved below). Press Ctrl+C to stop everything."
echo ""
wait
