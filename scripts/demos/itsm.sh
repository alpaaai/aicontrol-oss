#!/usr/bin/env bash
# One-shot runner for the ITSM demo scenario.
# Usage: scripts/demos/itsm.sh [fast|walkthrough]   (default: walkthrough)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODE="${1:-walkthrough}"
if [[ "$MODE" != "fast" && "$MODE" != "walkthrough" ]]; then
  echo "Error: mode must be 'fast' or 'walkthrough', got '$MODE'" >&2
  exit 1
fi

# Agent-scoped token for incident-response-agent (00000000-0000-0000-0000-000000000030).
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI0ZmUyOTE0YS1lYTMxLTRiNTgtOTMxZi0zOTAxYzVkZWIzMGQiLCJyb2xlIjoiYWdlbnQiLCJkZXNjcmlwdGlvbiI6ImRlbW8gc2NyaXB0IHRva2VuOiBpdHNtIn0.Ri8DRd2ORk8mbYdFJHDUF181uuMcLxYpzZpGSJOLmHM"

cd "$REPO_ROOT"
PYTHONPATH="$REPO_ROOT" "$REPO_ROOT/venv/bin/python" scripts/demos/run_demo.py \
  --scenario itsm --token "$TOKEN" --mode "$MODE"
