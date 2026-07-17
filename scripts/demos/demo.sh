#!/usr/bin/env bash
# One-shot runner for AIControl demo scenarios.
# Usage: scripts/demos/demo.sh <scenario|all> [fast|walkthrough]   (mode default: walkthrough)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <scenario|all> [fast|walkthrough]" >&2
  exit 1
fi

SCENARIO="$1"
MODE="${2:-walkthrough}"
if [[ "$MODE" != "fast" && "$MODE" != "walkthrough" ]]; then
  echo "Error: mode must be 'fast' or 'walkthrough', got '$MODE'" >&2
  exit 1
fi

source "$SCRIPT_DIR/tokens.env"

INTERCEPT_SCENARIOS=(lending healthcare itsm manufacturing support revops insurance)

run_one() {
  local name="$1"
  local mode="$2"
  local var_name
  var_name="TOKEN_$(echo "$name" | tr '[:lower:]' '[:upper:]')"
  local token="${!var_name:-}"
  if [[ -z "$token" || "$token" == REPLACE_WITH_* ]]; then
    echo "Error: set $var_name in $SCRIPT_DIR/tokens.env (currently unset or a placeholder)" >&2
    return 1
  fi
  PYTHONPATH="$REPO_ROOT" "$REPO_ROOT/venv/bin/python" "$SCRIPT_DIR/run_demo.py" \
    --scenario "$name" --token "$token" --mode "$mode"
}

if [[ "$SCENARIO" == "all" ]]; then
  declare -A RESULTS
  for name in "${INTERCEPT_SCENARIOS[@]}"; do
    echo ""
    echo "=================================================================="
    echo " Running: $name  (mode: $MODE)"
    echo "=================================================================="
    if run_one "$name" "$MODE"; then
      RESULTS["$name"]="PASS"
    else
      RESULTS["$name"]="FAIL"
    fi
  done

  echo ""
  echo "=================================================================="
  echo " Summary"
  echo "=================================================================="
  for name in "${INTERCEPT_SCENARIOS[@]}"; do
    printf "  %-15s %s\n" "$name" "${RESULTS[$name]}"
  done

  for name in "${INTERCEPT_SCENARIOS[@]}"; do
    if [[ "${RESULTS[$name]}" == "FAIL" ]]; then
      exit 1
    fi
  done
else
  run_one "$SCENARIO" "$MODE"
fi
