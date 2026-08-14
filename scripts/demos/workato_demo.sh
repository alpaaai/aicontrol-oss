#!/usr/bin/env bash
# One-script Workato FDE demo runner.
# Usage: scripts/demos/workato_demo.sh [fast|walkthrough]   (default: walkthrough)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MODE="${1:-walkthrough}"

BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

section() { echo ""; echo -e "${BOLD}=== $1 ===${NC}"; echo ""; }

section "Preflight"
_compose_service_healthy() {
  docker compose -p aicontrol ps --format json 2>/dev/null | python3 -c "
import json, sys
name = sys.argv[1]
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    row = json.loads(line)
    if row.get('Service') == name and row.get('Health') == 'healthy':
        sys.exit(0)
sys.exit(1)
" "$1"
}
if ! _compose_service_healthy postgres; then
  echo -e "${RED}Postgres is not healthy. Run: docker compose up -d${NC}" >&2
  exit 1
fi
if ! _compose_service_healthy opa; then
  echo -e "${RED}OPA is not healthy. Run: docker compose up -d${NC}" >&2
  exit 1
fi
if ! curl -s -o /dev/null http://localhost:8001/health; then
  echo -e "${RED}API is not reachable on :8001. Start it with bin/start-dev.sh (or: PYTHONPATH=$REPO_ROOT uvicorn app.main:app --port 8001 --host 0.0.0.0)${NC}" >&2
  exit 1
fi
if ! curl -s -o /dev/null -X POST http://localhost:8002/mcp/00000000-0000-0000-0000-000000000000/tools/list -d '{}' -H 'content-type: application/json'; then
  echo -e "${RED}MCP Native Proxy is not reachable on :8002. Start it with bin/start-dev.sh (or: uvicorn enterprise.mcp_gateway.main:gateway_app --port 8002 --host 0.0.0.0)${NC}" >&2
  exit 1
fi

# Default to the standard local scanner venv location (see docs/demos below)
# unless the user's shell/.env already sets these.
export SKILL_SCANNER_BINARY_PATH="${SKILL_SCANNER_BINARY_PATH:-$HOME/scanner-venvs/skill-scanner/bin/skill-scanner}"
export MCP_SCANNER_BINARY_PATH="${MCP_SCANNER_BINARY_PATH:-$HOME/scanner-venvs/mcp-scanner/bin/mcp-scanner}"
if [[ ! -x "$SKILL_SCANNER_BINARY_PATH" ]]; then
  echo -e "${YELLOW}Warning: $SKILL_SCANNER_BINARY_PATH not found -- skill scan step will fail.${NC}"
fi
if [[ ! -x "$MCP_SCANNER_BINARY_PATH" ]]; then
  echo -e "${YELLOW}Warning: $MCP_SCANNER_BINARY_PATH not found -- MCP server scan step will fail.${NC}"
fi
if [[ -z "${PROMPTFOO_BINARY_PATH:-}" ]]; then
  echo -e "${YELLOW}Warning: PROMPTFOO_BINARY_PATH not set (only used if you swap the red-team step off its subprocess-mocked demo).${NC}"
fi
echo -e "${GREEN}Preflight OK.${NC}"

source "$SCRIPT_DIR/tokens.env"

section "Clean junk data"
PYTHONPATH="$REPO_ROOT" "$REPO_ROOT/venv/bin/python" "$REPO_ROOT/scripts/demo_reset.py"

section "Seed"
PYTHONPATH="$REPO_ROOT" "$REPO_ROOT/venv/bin/python" "$REPO_ROOT/scripts/seed.py"

section "Start fixture MCP servers"
PYTHONPATH="$REPO_ROOT" "$REPO_ROOT/venv/bin/python" -m scripts.demos.fixture_servers start &
FIXTURE_PID=$!
sleep 4
cleanup() {
  pkill -f "scripts/demos/fixture_mcp_servers" 2>/dev/null
  kill "$FIXTURE_PID" 2>/dev/null
}
trap cleanup EXIT

section "1. Deterministic policy engine -- lending scenario"
"$SCRIPT_DIR/demo.sh" lending "$MODE"

section "2. Admission control -- skill and MCP server scanning"
PYTHONPATH="$REPO_ROOT" "$REPO_ROOT/venv/bin/python" "$SCRIPT_DIR/run_demo.py" \
  --scenario admission_scanning --token "$TOKEN_ADMISSION_SCANNING" --mode "$MODE"

section "3. MCP Native Proxy -- runtime enforcement"
PYTHONPATH="$REPO_ROOT" "$REPO_ROOT/venv/bin/python" "$SCRIPT_DIR/run_demo.py" \
  --scenario mcp_gateway --token "$TOKEN_MCP_GATEWAY" --mode "$MODE"

section "4. Red-teaming (promptfoo)"
PYTHONPATH="$REPO_ROOT" "$REPO_ROOT/venv/bin/python" "$SCRIPT_DIR/promptfoo_redteam_demo.py"

section "5. Outbound SIEM export"
AICONTROL_LICENSE_KEY="${AICONTROL_LICENSE_KEY:-business}" \
  PYTHONPATH="$REPO_ROOT" "$REPO_ROOT/venv/bin/python" "$SCRIPT_DIR/siem_export_demo.py"

section "Done"
echo "Dashboard: http://localhost:3000"
echo "Compliance / OWASP-NIST-EU AI Act control mapping: Dashboard -> Reports -> Generate Report"
