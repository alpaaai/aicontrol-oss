#!/usr/bin/env bash
# One-shot runner for the revops demo scenario.
# Usage: scripts/demos/revops.sh [fast|walkthrough]   (default: walkthrough)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODE="${1:-walkthrough}"
if [[ "$MODE" != "fast" && "$MODE" != "walkthrough" ]]; then
  echo "Error: mode must be 'fast' or 'walkthrough', got '$MODE'" >&2
  exit 1
fi

# Agent-scoped token for crm-automation-agent (00000000-0000-0000-0000-000000000060).
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI0OTQxOGI1NC1hNThmLTRhNDAtYTcxNS0wNTg1ZDRhNTQ1ODQiLCJyb2xlIjoiYWdlbnQiLCJkZXNjcmlwdGlvbiI6ImRlbW8gc2NyaXB0IHRva2VuOiByZXZvcHMifQ.RAUwjUm0grRHF525qQDIl7dZyIos6GHnItYKdPvnCBs"

cd "$REPO_ROOT"
PYTHONPATH="$REPO_ROOT" "$REPO_ROOT/venv/bin/python" scripts/demos/run_demo.py \
  --scenario revops --token "$TOKEN" --mode "$MODE"
