#!/usr/bin/env bash
# Runs the synthetic 30-day dashboard seed daily so demo dashboards never show
# a flat line / zero when a prospect joins unannounced. Idempotent — safe to
# run more than once a day (deterministic UUIDs, ON CONFLICT DO NOTHING).
# Requires: Postgres reachable (Docker Desktop). Not wired into bin/start-dev.sh
# because it's a data refresh, not a process to keep running.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"

cd "$REPO_ROOT"
source venv/bin/activate
PYTHONPATH="$REPO_ROOT" APP_ENV=production python3 scripts/demo_seed_synthetic.py \
  >> "$LOG_DIR/daily_seed_refresh.log" 2>&1
