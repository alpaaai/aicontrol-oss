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

- **OPA-based policy engine** — five rule types, evaluated before every tool call and
  pushed to OPA immediately on change (no restart):
  - `tool_denylist` — block specific tools outright
  - `tool_pattern` — block by name pattern, not just exact match
  - `rate_limit` — cap how many times a tool can be called in a window
  - `parameter_match` — condition a decision on specific argument values
  - `numeric_conditions` — condition a decision on numeric thresholds (e.g. amount > 10000)
- **Per-agent tool allowlists** — each agent has its own `approved_tools`, enforced
  independently of policy, so an agent can never call outside its own scope even if a
  policy would otherwise allow it.
- **Admission-time scanning** — scan a skill or tool for known-risky patterns before it's
  ever enrolled, via the built-in scanner integration (Cisco's open-source `skill-scanner`
  — see [Admission-time scanning](#admission-time-scanning) below).
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
- **Official Python SDK** — auto-instruments the Anthropic Claude Agent SDK, OpenAI Agents
  SDK, or Google ADK with no per-call code changes, or use a framework-agnostic decorator
  on any callable (see [Integration](#integration) below).
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
Your Agent ──► POST /intercept ──► OPA Policy Engine ──► allow / deny / review
                                           │
                                  Immutable Audit Log
                                     (PostgreSQL)
                                           │
                                  HITL Review Queue
```

---

## Integration

**Python — the official SDK (recommended):**

```bash
pip install "./sdk[anthropic]"   # or [openai], [google-adk] — installs from source
```

```python
from aicontrol_sdk import instrument

await instrument(agent_name="my-agent", url="http://localhost:8001", token="...")
# every tool call made through the detected framework (Anthropic Claude Agent SDK,
# OpenAI Agents SDK, or Google ADK) is now intercepted by AIControl before it executes.
```

Or use the framework-agnostic decorator on any callable:

```python
from aicontrol_sdk import control, PolicyDeniedError

@control("query_database")
async def query_database(table: str, limit: int = 100):
    return db.query(f"SELECT * FROM {table} LIMIT {limit}")

try:
    await query_database(table="customers")
except PolicyDeniedError as e:
    print(f"Blocked: {e.reason}")
```

`aicontrol-sdk` isn't published to PyPI yet — install it straight from the cloned repo, or
`pip install git+https://github.com/alpaaai/aicontrol-oss#subdirectory=sdk`. See
[`sdk/README.md`](sdk/README.md) for the full configuration reference.

**Any other language:** call `POST /intercept` directly — see
[aictl.io/docs/integration](https://aictl.io/docs/integration).

---

## Admission-time scanning

Before you enroll a new skill or tool, scan it:

```bash
curl -X POST http://localhost:8001/admission-scans \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"target_type": "skill", "target_ref": "/path/to/skill", "scanners": ["skill_scanner"]}'
```

Findings (with severity) show up in the response and in the dashboard's **Admission scans**
page. The default scanner runs
[Cisco's open-source `skill-scanner`](https://github.com/cisco-ai-defense/skill-scanner)
(Apache-2.0) as an isolated subprocess, deterministic analyzers only — no LLM calls, no
cloud calls, ever. See [`NOTICE`](NOTICE) for full attribution.

---

## Policy example

```json
{
  "name": "block_large_disbursements",
  "description": "Block loan disbursements above $10,000 without review",
  "rule_type": "tool_denylist",
  "condition": {
    "blocked_tools": ["initiate_transfer", "disburse_loan_funds"],
    "numeric_conditions": [
      { "parameter": "amount", "operator": "gt", "value": 10000 }
    ]
  },
  "action": "deny",
  "severity": "critical",
  "compliance_frameworks": ["SOC2", "OCC"]
}
```

Policies are pushed to OPA immediately through the API or dashboard — no restart required.
See [aictl.io/docs/policies](https://aictl.io/docs/policies) for all five rule types.

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
