# AIControl — The Control Plane for AI Agents

[![CI](https://github.com/alpaaai/aicontrol/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/alpaaai/aicontrol/actions)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

> Intercepts every AI agent tool call before execution. Evaluates against OPA policies.
> Logs everything to an append-only audit trail. Self-hosted — your data never leaves
> your environment.

---

## How It Works

```
  AI Agent
     │
     ▼
POST /intercept ──► OPA Policy Evaluation ──► allow / deny / review
     │                      │
     │              audit_events (append-only)
     │                      │
     ▼                      ▼
  Agent gets         React Dashboard
  decision           (port 3000)
```

One API call in your agent's tool execution path.
Policies evaluated in under 10ms. Every decision logged — no exceptions.

---

## Quick Start

```bash
git clone https://github.com/alpaaai/aicontrol
cd aicontrol
cp .env.example .env          # set POSTGRES_PASSWORD, optional SLACK_BOT_TOKEN
bash install.sh               # pull images, run migrations, seed demo agents + tokens
bash scripts/quickstart.sh    # seed demo data, run lending scenario, open dashboard
```

**First-time setup:** Open `http://localhost:3000` — the setup wizard runs automatically on first launch. Set your organisation name, timezone, and root admin email + password. After setup, login with those credentials.

**Dashboard:** http://localhost:3000
**API docs:** http://localhost:8001/docs
**Health:** http://localhost:8001/health

---

## Plans

| Feature | Community | Business | Enterprise |
|---------|-----------|----------|------------|
| OPA policy enforcement (deterministic) | ✅ | ✅ | ✅ |
| Per-agent approved_tools enforcement | ✅ | ✅ | ✅ |
| Rate-based policies (session + rolling window) | ✅ | ✅ | ✅ |
| Append-only audit log (7-day retention) | ✅ | — | — |
| Append-only audit log (1-year retention) | — | ✅ | ✅ |
| React dashboard | ✅ | ✅ | ✅ |
| First-run setup wizard | ✅ | ✅ | ✅ |
| User management (invite, deactivate, reset password) | ✅ | ✅ | ✅ |
| Policy library (18 pre-built templates) | ✅ | ✅ | ✅ |
| Baseline activation wizard | ✅ | ✅ | ✅ |
| HITL review queue (in-dashboard) | ✅ | ✅ | ✅ |
| Slack HITL notifications | — | ✅ | ✅ |
| Audit log CSV export | — | — | ✅ |
| OPA health-watch + observability dashboard | — | — | ✅ |
| Policy drift detection + warning feed | — | — | ✅ |
| Compliance report export (PDF — SOC 2, HIPAA, GLBA) | — | — | ✅ |

**Business:** $49/month + $15 per million intercepts. Contact: hello@aictl.io
**Enterprise:** $149/month + $25.25 per million intercepts. Contact: hello@aictl.io

To enable Business or Enterprise features, add `AICONTROL_LICENSE_KEY=your-key` to `.env` and restart:

```bash
docker compose -f docker-compose.yml -f docker-compose.app.yml up -d
```

License is read from the API at runtime — no frontend rebuild required.

---

## Components

| Component | Image | Port |
|-----------|-------|------|
| API (FastAPI) | `ghcr.io/alpaaai/aicontrol-api:latest` | 8001 |
| React Dashboard | `ghcr.io/alpaaai/aicontrol-frontend:latest` | 3000 |
| OPA (policy engine) | `openpolicyagent/opa:latest-debug` | 8181 |
| PostgreSQL 15 | `postgres:15` | 5432 |

Two Docker Compose files:
- `docker-compose.yml` — infrastructure (Postgres + OPA)
- `docker-compose.app.yml` — application (API + React dashboard)

---

## Integration

```python
import httpx

response = httpx.post(
    "http://aicontrol:8001/intercept",
    headers={"Authorization": f"Bearer {AICONTROL_TOKEN}"},
    json={
        "session_id": session_id,
        "agent_id": agent_id,
        "agent_name": "my-agent",
        "tool_name": tool_name,
        "tool_parameters": tool_parameters,
        "sequence_number": seq,
    }
)
decision = response.json()["decision"]  # "allow" | "deny" | "review"
```

Framework wrappers: LangChain, CrewAI, OpenAI Agents SDK, AutoGen, MCP.
See [aictl.io/docs/integration](https://aictl.io/docs/integration).

---

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `bash install.sh` | First-time setup — images, migrations, seed agents, issue tokens |
| `bash scripts/quickstart.sh` | Demo-ready — V2 seed data, run demo, open browser |
| `bash verify.sh` | Health checks — all components |
| `bash diagnose.sh` | Debug output for support |
| `python scripts/seed.py` | Seed demo agents and policies (idempotent) |
| `python scripts/demo_reset.py` | Reset audit log for clean demo run |
| `python scripts/demos/run_demo.py --scenario lending` | Run industry demo |

---

## Documentation

**[aictl.io/docs](https://aictl.io/docs)**

---

## License

Apache 2.0 — community edition.
Enterprise features require a license key. Contact hello@aictl.io.
