#!/usr/bin/env bash
# Starts API, MCP gateway, dashboard, and demo fixture servers in the foreground.
# Assumes Postgres + OPA are already running (e.g. via Docker Desktop).
# Ctrl+C stops everything this script started.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Checking Postgres + OPA..."
if ! docker compose ps --status running 2>/dev/null | grep -q postgres; then
  echo "    WARNING: postgres container not detected as running (check Docker Desktop)." >&2
fi
if ! docker compose ps --status running 2>/dev/null | grep -q opa; then
  echo "    WARNING: opa container not detected as running (check Docker Desktop)." >&2
fi

source venv/bin/activate
export PYTHONPATH="$REPO_ROOT"

SKILL_SCANNER_BIN="$REPO_ROOT/.scanner-venvs/skill-scanner/bin/skill-scanner"
MCP_SCANNER_BIN="$REPO_ROOT/.scanner-venvs/mcp-scanner/bin/mcp-scanner"
if [[ -x "$SKILL_SCANNER_BIN" ]]; then
  export SKILL_SCANNER_BINARY_PATH="$SKILL_SCANNER_BIN"
else
  echo "    WARNING: $SKILL_SCANNER_BIN not found — admission scan (skill) will fail." >&2
fi
if [[ -x "$MCP_SCANNER_BIN" ]]; then
  export MCP_SCANNER_BINARY_PATH="$MCP_SCANNER_BIN"
else
  echo "    WARNING: $MCP_SCANNER_BIN not found — admission scan (MCP server) will fail." >&2
fi

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

echo "==> Starting API on :8001"
uvicorn app.main:app --reload --port 8001 --host 0.0.0.0 &
PIDS+=("$!")

echo "==> Starting MCP gateway on :8002"
uvicorn enterprise.mcp_gateway.main:gateway_app --port 8002 --host 0.0.0.0 &
PIDS+=("$!")

echo "==> Starting dashboard on :3000"
(cd frontend && npm run dev) &
PIDS+=("$!")

echo "==> Starting demo fixture servers on :8901 :8902 :8903"
python3 docs/demos/fixtures/mcp_server_malicious.py &
PIDS+=("$!")
python3 docs/demos/fixtures/mcp_server_benign.py &
PIDS+=("$!")
python3 docs/demos/fixtures/gateway_downstream_stub.py &
PIDS+=("$!")

echo ""
echo "==> All processes running (output interleaved below). Press Ctrl+C to stop everything."
echo ""
wait
