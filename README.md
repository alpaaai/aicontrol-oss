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

- **OPA-based policy enforcement** — every tool call evaluated before execution
- **Immutable audit trail** — every decision logged with full parameters and policy attribution
- **Human-in-the-loop review queue** — escalate to a human reviewer when policy requires it
- **Self-hosted, one command** — runs on your infrastructure, no cloud dependency

---

## Quick start

```bash
git clone https://github.com/alpaaai/aicontrol-oss
cd aicontrol-oss
bash install.sh
# Dashboard → http://localhost:3000
# API       → http://localhost:8001
```

`install.sh` generates a `.env` with real secrets, pulls images, runs
database migrations, and seeds demo agents — a bare `docker compose up`
skips all of that (it also won't start the API or dashboard at all, since
those live in `docker-compose.app.yml`, not the default compose file).

Want 30 days of realistic historical activity in the dashboard instead of
a blank audit log? After `install.sh` finishes:

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
                              HITL Review Queue (Slack / Teams)
```

---

## Integration

```python
from aicontrol import control

@control
def create_purchase_order(vendor_id: str, amount: float) -> dict:
    # AIControl evaluates this call against your policies before it runs
    ...
```

Set `AICONTROL_URL`, `AICONTROL_TOKEN`, and `AICONTROL_AGENT_ID` in your environment.
That's the entire integration.

---

## Policy example

```yaml
- name: require_approval_large_purchase_order
  description: "Purchase orders above $50,000 require human approval before submission"
  rule_type: tool_denylist
  condition:
    tool_name: submit_purchase_order
    numeric_conditions:
      - parameter: amount
        operator: gt
        value: 50000
    on_exceed: review
  active: true
  compliance_tags: ["SOC2", "internal-controls"]
```

Policies are YAML, enforced by OPA, pushed live without restart.

---

## Enterprise edition

AIControl Community is MIT-licensed and fully self-hostable.
AIControl Enterprise adds the compliance evidence package, RBAC, and dedicated support.
[Learn more at aictl.io](https://aictl.io)

---

## Links

- Documentation: https://aictl.io/docs
- Issues: https://github.com/alpaaai/aicontrol-oss/issues
- Design Partner Program: https://aictl.io/design-partners
