#!/usr/bin/env bash
# Runs every demo scenario in sequence.
# Usage: scripts/demos/run_all.sh [fast|walkthrough]   (default: walkthrough)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODE="${1:-walkthrough}"
if [[ "$MODE" != "fast" && "$MODE" != "walkthrough" ]]; then
  echo "Error: mode must be 'fast' or 'walkthrough', got '$MODE'" >&2
  exit 1
fi

SCENARIOS=(lending healthcare itsm manufacturing support revops insurance)

declare -A RESULTS
for name in "${SCENARIOS[@]}"; do
  echo ""
  echo "=================================================================="
  echo " Running: $name  (mode: $MODE)"
  echo "=================================================================="
  if "$SCRIPT_DIR/$name.sh" "$MODE"; then
    RESULTS["$name"]="PASS"
  else
    RESULTS["$name"]="FAIL"
  fi
done

echo ""
echo "=================================================================="
echo " Summary"
echo "=================================================================="
for name in "${SCENARIOS[@]}"; do
  printf "  %-15s %s\n" "$name" "${RESULTS[$name]}"
done

for name in "${SCENARIOS[@]}"; do
  if [[ "${RESULTS[$name]}" == "FAIL" ]]; then
    exit 1
  fi
done
