# AIControl — Getting Started

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
  - Linux: `curl -fsSL https://get.docker.com | sh`
  - macOS / Windows: Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) — Compose v2 included
- Ubuntu 22.04+ or macOS (Apple Silicon / arm64 supported)
- 2 GB RAM minimum, 4 GB recommended
- Ports 8001 (API) and 8501 (dashboard) available

## Installation

```bash
git clone https://github.com/alpaaai/aicontrol.git
cd aicontrol
bash install.sh
```

The installer will:
1. Prompt for your database password and Slack credentials (optional)
2. Pull the latest Docker images from ghcr.io
3. Run database migrations
4. Seed 7 demo agents
5. Issue an admin token
6. Issue 7 agent-scoped demo tokens (one per scenario)
7. Save all tokens to `.env`

**Save the admin token shown on screen — it is also written to `.env`.**

After install, run:
```bash
bash verify.sh
```

Expected output: `8 passed, 0 failed`.

## Accessing AIControl

| Service   | URL                          |
|-----------|------------------------------|
| Dashboard | http://localhost:8501        |
| API       | http://localhost:8001        |
| API docs  | http://localhost:8001/docs   |
| Health    | http://localhost:8001/health |

## Running a demo

```bash
source .env
python scripts/demos/run_demo.py \
  --scenario insurance --token $DEMO_TOKEN_INSURANCE --mode fast
```

Expected output: `allow → allow → review → deny`

Available scenarios: `lending`, `healthcare`, `itsm`, `manufacturing`, `support`, `revops`, `insurance`

## Your first intercept call

Port 8001. Use any UUID for `session_id` and `agent_id`. Sessions are created automatically on the first intercept call — no pre-registration required.

**Allow — `read_file`:**

```bash
curl -X POST http://localhost:8001/intercept \
  -H "Authorization: Bearer <agent-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "00000000-0000-0000-0000-000000000001",
    "agent_id":   "00000000-0000-0000-0000-000000000002",
    "agent_name": "my-agent",
    "tool_name":  "read_file",
    "tool_parameters": {"path": "/data/report.csv"},
    "sequence_number": 1
  }'
```

Response: `{"decision": "allow", ...}`

**Deny — `shell_exec`:**

```bash
curl -X POST http://localhost:8001/intercept \
  -H "Authorization: Bearer <agent-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "00000000-0000-0000-0000-000000000001",
    "agent_id":   "00000000-0000-0000-0000-000000000002",
    "agent_name": "my-agent",
    "tool_name":  "shell_exec",
    "tool_parameters": {"command": "ls /"},
    "sequence_number": 2
  }'
```

Response: `{"decision": "deny", "reason": "tool_denylisted", ...}`

## Default policies

11 policies are active after installation. See [aictl.io/docs/policies](https://aictl.io/docs/policies) for the full list with conditions and examples.

## Managing tokens

Issue a token:
```bash
docker compose -f docker-compose.yml -f docker-compose.app.yml \
  exec api python scripts/issue_token.py --role agent --desc "Agent name"
```

Revoke a token:
```bash
docker compose -f docker-compose.yml -f docker-compose.app.yml \
  exec api python scripts/revoke_token.py --id <TOKEN_UUID>
```

Or use the **Tokens** tab in the dashboard.

Demo tokens are already in `.env` as `DEMO_TOKEN_<SCENARIO>` (e.g. `DEMO_TOKEN_LENDING`, `DEMO_TOKEN_INSURANCE`).

## Updating AIControl

```bash
docker compose -f docker-compose.yml -f docker-compose.app.yml pull
docker compose -f docker-compose.yml -f docker-compose.app.yml up -d
docker compose -f docker-compose.yml -f docker-compose.app.yml \
  exec api alembic upgrade head
```

## Troubleshooting

Run the diagnostic collector and share the output with support:
```bash
bash diagnose.sh
```

| Symptom | Likely cause | Fix |
|---|---|---|
| `install.sh` fails at image pull | Not logged into ghcr.io | `docker login ghcr.io` |
| API container exits immediately | Bad `DATABASE_URL` in `.env` | Check postgres hostname is `postgres` not `localhost` |
| Dashboard can't reach API | Wrong network config | Verify both compose files use `aicontrol` network |
| `verify.sh` dashboard check fails | Dashboard slow to start | Wait 15s then re-run |
| GitHub Actions build fails | `GITHUB_TOKEN` permissions | Repo Settings → Actions → Allow write permissions |
| Image not found on ghcr.io | Package visibility private | GitHub → Packages → Change visibility to public |
| `alembic upgrade head` fails in container | Migrations not copied | Check `COPY migrations/` in Dockerfile |
| Port 8001 in use | Another process on 8001 | `lsof -i :8001` then kill the process |
| `ADMIN_TOKEN` not set | `.env` not sourced | `source .env` |
| `DEMO_TOKEN_*` not set | `install.sh` not run | Re-run `bash install.sh` |
| Dashboard `ModuleNotFoundError` | Old image cached | `docker compose pull` then restart |
| `ERROR: Unsupported operating system 'macOS'` | Used Linux install script on macOS | Install Docker Desktop instead: docker.com/products/docker-desktop |
