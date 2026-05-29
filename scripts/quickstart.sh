#!/usr/bin/env bash
# AIControl Quick Start
# Run after install.sh: bash scripts/quickstart.sh
# Gets you from running stack to demo-ready in under 2 minutes.
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

COMPOSE="-f docker-compose.yml -f docker-compose.app.yml"

# Load .env
if [ ! -f .env ]; then
  echo "ERROR: .env not found. Run bash install.sh first."
  exit 1
fi
set -a; source .env; set +a

echo ""
echo -e "${BOLD}=== AIControl Quick Start ===${NC}"
echo ""

# Print URLs and admin token
echo -e "${CYAN}  API:         http://localhost:8001${NC}"
echo -e "${CYAN}  Dashboard:   http://localhost:3000${NC}"
echo -e "${CYAN}  API docs:    http://localhost:8001/docs${NC}"
echo ""
echo -e "${YELLOW}  Admin token: ${ADMIN_TOKEN:-[not set — run install.sh]}${NC}"
echo ""
echo -e "  Use the admin token directly with the API (curl, httpx, etc.)"
echo -e "  Dashboard login uses email OTP — see aictl.io/docs/operations for email setup."
echo ""

# Seed V2 demo data (idempotent)
echo "[1/3] Seeding V2 demo data..."
docker compose $COMPOSE exec -T api python3 scripts/seed.py
echo -e "${GREEN}[done]${NC} Agents, policies, and V2 features seeded."

# Run lending demo to populate audit log
echo ""
echo "[2/3] Running lending demo (populates audit log)..."
if [ -z "${DEMO_TOKEN_LENDING:-}" ]; then
  echo -e "${YELLOW}Warning: DEMO_TOKEN_LENDING not set in .env.${NC}"
  echo "  Skipping demo run. Run install.sh to generate tokens."
else
  docker compose $COMPOSE exec -T api \
    python3 scripts/demos/run_demo.py \
    --scenario lending \
    --token "$DEMO_TOKEN_LENDING" \
    --mode fast
fi
echo -e "${GREEN}[done]${NC} Audit log populated."

# Open browser
echo ""
echo "[3/3] Opening dashboard..."
DASHBOARD_URL="http://localhost:3000"

# Detect WSL2 vs Linux vs macOS
if uname -r | grep -qi microsoft; then
  # WSL2 — use Windows explorer.exe
  cmd.exe /c start "$DASHBOARD_URL" 2>/dev/null || true
elif command -v xdg-open &>/dev/null; then
  # Linux
  xdg-open "$DASHBOARD_URL" 2>/dev/null || true
elif command -v open &>/dev/null; then
  # macOS
  open "$DASHBOARD_URL" 2>/dev/null || true
fi

echo ""
echo -e "${BOLD}${GREEN}=== Ready ===${NC}"
echo ""
echo "  Dashboard: $DASHBOARD_URL"
echo "  Audit log shows lending demo intercepts (3 ALLOW, 2 DENY)."
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Open Dashboard → Audit Log — filter by DENY to see denied calls"
echo "  2. Open Dashboard → Policies — see rate-limit and approved_tools policies"
if [ -n "${AICONTROL_LICENSE_KEY:-}" ]; then
  echo "  3. Open Dashboard → Governance → Warnings — see drift detection"
  echo "  4. Open Dashboard → Reports — generate a compliance report"
else
  echo "  3. For enterprise features (drift detection, compliance reports):"
  echo "     Set AICONTROL_LICENSE_KEY + VITE_ENTERPRISE=true in .env"
  echo "     Then: docker compose $COMPOSE build frontend && docker compose $COMPOSE up -d"
fi
echo ""
echo "  Full demo walkthrough: scripts/demos/demo-walkthrough-v2.md"
echo "  Docs: https://aictl.io/docs"
echo ""
