#!/usr/bin/env bash
# AIControl Install Script
# Run from the repo root: bash install.sh
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${BOLD}=== AIControl Installer ===${NC}"
echo ""

# Check dependencies
for cmd in docker curl python3; do
  if ! command -v "$cmd" &>/dev/null; then
    echo -e "${RED}ERROR: $cmd is required but not installed.${NC}"
    exit 1
  fi
done
if ! docker compose version &>/dev/null; then
  echo -e "${RED}ERROR: docker compose v2 is required.${NC}"
  exit 1
fi

# Generate or load .env
if [ -f .env ]; then
  echo -e "${YELLOW}[skip]${NC} .env already exists — using existing configuration."
  echo "       Delete .env to reconfigure from scratch."
  echo ""
  python3 scripts/check_env_completeness.py .env || true
else
  echo -e "${BOLD}Let's configure AIControl.${NC}"
  echo ""

  read -rp "PostgreSQL password (default: auto-generated): " DB_PASS
  DB_PASS=${DB_PASS:-$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")}

  read -rp "Secret key for JWT signing (default: auto-generated): " SECRET_KEY
  SECRET_KEY=${SECRET_KEY:-$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")}

  read -rp "Slack bot token (xoxb-..., or press Enter to skip): " SLACK_TOKEN
  SLACK_TOKEN=${SLACK_TOKEN:-xoxb-placeholder}

  read -rp "Slack signing secret (or press Enter to skip): " SLACK_SECRET
  SLACK_SECRET=${SLACK_SECRET:-placeholder}

  read -rp "Slack review channel (default: #aicontrol-reviews): " SLACK_CHANNEL
  SLACK_CHANNEL=${SLACK_CHANNEL:-#aicontrol-reviews}

  echo ""
  echo "AI-native features (e.g. compliance report export) call an LLM through your"
  echo "own account. Press Enter to accept defaults and evaluate with mock LLM output."
  read -rp "LLM provider (default: anthropic): " LLM_PROVIDER
  LLM_PROVIDER=${LLM_PROVIDER:-anthropic}

  read -rp "LLM model (default: claude-haiku-4-5-20251001): " LLM_MODEL
  LLM_MODEL=${LLM_MODEL:-claude-haiku-4-5-20251001}

  read -rp "LLM API key (press Enter to skip and use mock mode): " LLM_API_KEY
  if [ -z "$LLM_API_KEY" ]; then
    LLM_MOCK_ENABLED=true
    echo -e "${YELLOW}[info]${NC} No LLM API key given — LLM_MOCK_ENABLED=true."
    echo "       AI-native features (e.g. compliance export) will return mock output"
    echo "       until you set LLM_API_KEY and LLM_MOCK_ENABLED=false in .env."
  else
    LLM_MOCK_ENABLED=false
  fi

  cat > .env << ENVEOF
# PostgreSQL
POSTGRES_USER=aicontrol
POSTGRES_PASSWORD=${DB_PASS}
POSTGRES_DB=aicontrol
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# SQLAlchemy
DATABASE_URL=postgresql+asyncpg://aicontrol:${DB_PASS}@postgres:5432/aicontrol

# App
APP_ENV=production
SECRET_KEY=${SECRET_KEY}

# Slack HITL
SLACK_BOT_TOKEN=${SLACK_TOKEN}
SLACK_SIGNING_SECRET=${SLACK_SECRET}
SLACK_REVIEW_CHANNEL=${SLACK_CHANNEL}

# React dashboard env vars (baked into frontend image at build time)
VITE_API_URL=http://localhost:8001

# CORS — comma-separated allowed origins for React dashboard. Change for remote deployments.
CORS_ORIGINS=http://localhost:3000

# AI-native features — LLM calls use your own account, never billed by AIControl.
# LLM_MOCK_ENABLED=true returns mock output so every AI-native feature (e.g.
# compliance report export) works without a real API key.
LLM_PROVIDER=${LLM_PROVIDER}
LLM_MODEL=${LLM_MODEL}
LLM_API_KEY=${LLM_API_KEY}
LLM_MOCK_ENABLED=${LLM_MOCK_ENABLED}
ENVEOF

  echo ""
  echo -e "${GREEN}[done]${NC} .env created."
fi

# Pull images
echo ""
echo "[1/4] Pulling Docker images..."
docker compose -f docker-compose.yml -f docker-compose.app.yml pull --quiet --ignore-pull-failures || true
echo -e "${GREEN}[done]${NC} Images pulled (or using cached versions)."

# Start infra first
echo "[2/4] Starting infrastructure (postgres)..."
docker compose -f docker-compose.yml up -d
echo -e "      Waiting for postgres..."
for i in $(seq 1 30); do
  if docker compose -f docker-compose.yml exec -T postgres \
     pg_isready -U aicontrol -d aicontrol &>/dev/null; then
    break
  fi
  sleep 2
  [ "$i" -eq 30 ] && { echo -e "${RED}ERROR: Postgres not ready.${NC}"; exit 1; }
done
echo -e "${GREEN}[done]${NC} Infrastructure ready."

# Run migrations
echo "[3/4] Running database migrations..."
docker compose -f docker-compose.yml -f docker-compose.app.yml \
  run --rm api alembic upgrade head
echo -e "${GREEN}[done]${NC} Migrations applied."

# Start app services
echo "[4/4] Starting application services (api, frontend)..."
docker compose -f docker-compose.yml -f docker-compose.app.yml up -d
echo -e "${GREEN}[done]${NC} All services started."

echo ""
echo -e "${BOLD}${GREEN}=== Installation complete ===${NC}"
echo ""
echo "  API:       http://localhost:8001"
echo "  Dashboard: http://localhost:3000"
echo "  Health:    http://localhost:8001/health"
echo ""
echo "Next: open http://localhost:3000 to run the first-run setup wizard"
echo "      and create your admin account."
echo ""
echo "Want fictional demo data instead? Run: bash scripts/seed_demo.sh"
echo ""
