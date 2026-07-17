#!/usr/bin/env bash
# One-shot runner for the support demo scenario.
# Usage: scripts/demos/support.sh [fast|walkthrough]   (default: walkthrough)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODE="${1:-walkthrough}"
if [[ "$MODE" != "fast" && "$MODE" != "walkthrough" ]]; then
  echo "Error: mode must be 'fast' or 'walkthrough', got '$MODE'" >&2
  exit 1
fi

# Agent-scoped token for support-resolution-agent (00000000-0000-0000-0000-000000000050).
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiIyOGQ0YTZiZC1mZGE2LTQ4NTUtYjVmNS1hMTI1MzFhNWQzN2YiLCJyb2xlIjoiYWdlbnQiLCJkZXNjcmlwdGlvbiI6ImRlbW8gc2NyaXB0IHRva2VuOiBzdXBwb3J0In0.s9jVa5QyLzpurfxlEVmeuTr4Nt1w029YBF3poUcCoos"

cd "$REPO_ROOT"
PYTHONPATH="$REPO_ROOT" "$REPO_ROOT/venv/bin/python" scripts/demos/run_demo.py \
  --scenario support --token "$TOKEN" --mode "$MODE"
