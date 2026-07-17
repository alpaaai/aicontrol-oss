#!/usr/bin/env bash
# One-shot runner for the lending demo scenario.
# Usage: scripts/demos/lending.sh [fast|walkthrough]   (default: walkthrough)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODE="${1:-walkthrough}"
if [[ "$MODE" != "fast" && "$MODE" != "walkthrough" ]]; then
  echo "Error: mode must be 'fast' or 'walkthrough', got '$MODE'" >&2
  exit 1
fi

# Agent-scoped token for loan-underwriting-agent (00000000-0000-0000-0000-000000000010).
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJhNDQyYzg5Mi1hYjJhLTQ5NDgtYjgyOC05YzY0ZDZkOTJmZjgiLCJyb2xlIjoiYWdlbnQiLCJkZXNjcmlwdGlvbiI6ImRlbW8gc2NyaXB0IHRva2VuOiBsZW5kaW5nIn0.1AEleIkwDznI4CRiIceO6yxiNgwJIvfUYGvqaEqszOo"

cd "$REPO_ROOT"
PYTHONPATH="$REPO_ROOT" "$REPO_ROOT/venv/bin/python" scripts/demos/run_demo.py \
  --scenario lending --token "$TOKEN" --mode "$MODE"
