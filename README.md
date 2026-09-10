# AIControl — Runtime Governance for AI Agents

![License](https://img.shields.io/badge/license-MIT-blue)
![Docker](https://img.shields.io/badge/docker-ready-brightgreen)
![Python](https://img.shields.io/badge/python-3.14-blue)

---

AI agents are now handling purchasing decisions, customer refunds, clinical documentation,
and infrastructure changes. Security teams have one question: what stops them from doing
something they shouldn't. AIControl sits between your agents and their tools — every call
evaluated against policy before execution, every decision logged, nothing escalated without
a human sign-off.

---

## Features

- **Cedar policy engine, in-process** — evaluated before every tool call; policies
  are recompiled immediately on change (no restart, no sidecar):
  - `tool_denylist` — block specific tools outright
  - `tool_pattern` — block by name pattern, not just exact match
  - `rate_limit` — cap how many times a tool can be called in a window
  - `parameter_match` — condition a decision on specific argument values
  - `numeric_conditions` — condition a decision on numeric thresholds (e.g. amount > 10000)
- **Per-agent tool allowlists** — each agent has its own `approved_tools`, enforced
  independently of policy, so an agent can never call outside its own scope even if a
  policy would otherwise allow it.
- **Immutable audit trail** — every intercepted call writes an `audit_event` regardless of
  the decision (allow, deny, or review) — append-only, with the full parameters and which
  policy fired.
- **Human-in-the-loop review queue** — policies can route a call to a human reviewer
  instead of an automatic allow/deny; every review is created and recorded regardless of
  plan. Viewing and resolving the queue from the dashboard's Reviews page, and viewing
  session drill-down, both require an Enterprise license (see
  [Enterprise edition](#enterprise-edition) below).
- **Per-agent observe mode** — set an agent's `governance_mode` to `observe` and its
  policy decisions are recorded exactly as if enforced, but never actually block a call —
  useful for rolling out a new policy set risk-free before switching it to enforce.
- **React dashboard** — first-run setup wizard, a live activity/audit feed, agent and
  token management, a policy library of pre-built templates, and a no-JSON policy editor.
- **MCP gateway** — point any MCP-client-capable agent framework at AIControl's gateway
  endpoint instead of the downstream MCP server directly; AIControl evaluates policy and
  audits every `tools/list` and `tools/call` on the wire before forwarding (see
  [Integration](#integration) below).
- **Self-hosted, one command** — runs on your own infrastructure, no cloud dependency.

---

## Quick start

```bash
git clone https://github.com/alpaaai/aicontrol-oss
cd aicontrol-oss
bash install.sh
# Dashboard → http://localhost:3000
# API       → http://localhost:8001
```

`install.sh` walks you through generating a `.env` with real secrets, pulls the prebuilt
images, runs database migrations, and seeds demo agents — a bare `docker compose up` skips
all of that (it also won't start the API or dashboard at all, since those live in
`docker-compose.app.yml`, not the default compose file).

**First run:** open `http://localhost:3000` — the setup wizard runs automatically. Set your
organisation name, timezone, and root admin email + password, then log in with those
credentials.

Want 30 days of realistic historical activity in the dashboard instead of a blank audit log?
After `install.sh` finishes:

```bash
docker compose -f docker-compose.yml -f docker-compose.app.yml -f docker-compose.demo.yml up demo-seed
```

---

## How it works

```
Your Agent ──► AIControl Gateway ──► Cedar Policy Engine ──► allow / deny / review
             (MCP tools/list, call)          │
                                     Immutable Audit Log
                                        (PostgreSQL)
                                              │
                                     HITL Review Queue
```

---

## Integration

Point your agent's MCP client at AIControl's gateway endpoint instead of the
downstream MCP server directly. Register the downstream server once
(`POST /mcp-servers`, admin-only):

```bash
curl -X POST http://localhost:8001/mcp-servers \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "invoicing-mcp", "base_url": "https://invoicing.internal/mcp", "approved_tools": ["get_invoice", "create_invoice"]}'
# -> {"id": "<server_id>", "status": "pending_review", ...}

curl -X PATCH http://localhost:8001/mcp-servers/<server_id> \
  -H "Authorization: Bearer <admin-token>" \
  -d '{"status": "active"}'
```

Then point the agent's MCP client at `http://localhost:8001/mcp/<server_id>/`
with an agent-scoped bearer token (`scripts/onboard_agent.py` issues one).
AIControl evaluates Cedar policy on every `tools/list` and `tools/call`,
audits the result, and forwards allowed calls to the real downstream server.

**Any MCP-client-capable framework works with zero AIControl-specific code** —
this is true by construction, not a per-framework certification: it does not
confirm that any specific framework's MCP client mode supports custom auth
header injection or retry semantics compatible with this gateway. This
replaces the previous `aicontrol-sdk` package and `instrument()`/`@control`
model, which has been removed.

**Any other language or protocol:** any MCP-client library works against the
gateway endpoint above — see [aictl.io/docs/integration](https://aictl.io/docs/integration).

---

## Policy example

```json
{
  "name": "block_large_disbursements",
  "description": "Block loan disbursements above $10,000 without review",
  "condition": {
    "blocked_tools": ["initiate_transfer", "disburse_loan_funds"],
    "numeric_conditions": [
      { "parameter": "amount", "operator": "gt", "value": 10000 }
    ]
  },
  "effect": "deny",
  "severity": "critical",
  "compliance_frameworks": ["SOC2", "OCC"]
}
```

Policies are recompiled immediately through the API or dashboard — no restart required.
See [aictl.io/docs/policies](https://aictl.io/docs/policies) for all supported condition keys.

---

## Enterprise edition

AIControl Community is MIT-licensed, free, and fully self-hostable — no seat limits, no
usage limits. AIControl Enterprise adds the in-dashboard HITL review queue (viewing and
resolving reviews), session view/drill-down, audit log CSV export, policy drift detection,
and compliance report generation. [Learn more at aictl.io](https://aictl.io)

---

## Links

- Documentation: https://aictl.io/docs
- Issues: https://github.com/alpaaai/aicontrol-oss/issues
