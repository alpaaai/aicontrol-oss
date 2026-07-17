#!/usr/bin/env bash
# One-shot runner for the insurance demo scenario.
# Usage: scripts/demos/insurance.sh [fast|walkthrough]   (default: walkthrough)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODE="${1:-walkthrough}"
if [[ "$MODE" != "fast" && "$MODE" != "walkthrough" ]]; then
  echo "Error: mode must be 'fast' or 'walkthrough', got '$MODE'" >&2
  exit 1
fi

# Already-issued agent-scoped token for insurance-claims-agent — paste it below.
TOKEN="REPLACE_WITH_INSURANCE_TOKEN"

if [[ -z "$TOKEN" || "$TOKEN" == "REPLACE_WITH_INSURANCE_TOKEN" ]]; then
  echo "Error: set your insurance agent token in $0 (TOKEN=...)" >&2
  exit 1
fi

cd "$REPO_ROOT"
PYTHONPATH="$REPO_ROOT" "$REPO_ROOT/venv/bin/python" scripts/demos/run_demo.py \
  --scenario insurance --token "$TOKEN" --mode "$MODE"
