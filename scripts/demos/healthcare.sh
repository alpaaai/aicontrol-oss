#!/usr/bin/env bash
# One-shot runner for the healthcare demo scenario.
# Usage: scripts/demos/healthcare.sh [fast|walkthrough]   (default: walkthrough)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODE="${1:-walkthrough}"
if [[ "$MODE" != "fast" && "$MODE" != "walkthrough" ]]; then
  echo "Error: mode must be 'fast' or 'walkthrough', got '$MODE'" >&2
  exit 1
fi

# Agent-scoped token for clinical-documentation-agent (00000000-0000-0000-0000-000000000020).
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJmZjY4MmZmZi02ZDM5LTQyOTktOTMyOS1mMzMxODkxNzBkYzEiLCJyb2xlIjoiYWdlbnQiLCJkZXNjcmlwdGlvbiI6ImRlbW8gc2NyaXB0IHRva2VuOiBoZWFsdGhjYXJlIn0.j652AaNo8lRH-N3rwlNEaTGelGvfofW5JPzgzEm0KTM"

cd "$REPO_ROOT"
PYTHONPATH="$REPO_ROOT" "$REPO_ROOT/venv/bin/python" scripts/demos/run_demo.py \
  --scenario healthcare --token "$TOKEN" --mode "$MODE"
