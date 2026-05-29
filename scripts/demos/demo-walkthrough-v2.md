# AIControl V2 — 10-Minute CISO Walkthrough
<!-- For: Aon, financial services prospects, healthcare CISOs -->
<!-- Stack: running Docker Compose, AICONTROL_LICENSE_KEY set for enterprise features -->
<!-- Pre-demo: bash scripts/quickstart.sh already run — audit log populated -->

---

## Setup (before prospect joins — 2 minutes)

```bash
# Confirm stack is running
curl -s http://localhost:8001/health | python3 -m json.tool
# Expected: "status": "ok", "opa_status": "healthy"

# Reset and re-seed clean state
docker compose exec api python scripts/demo_reset.py
docker compose exec api python scripts/seed.py

# Open browser to React dashboard
# http://localhost:3000
# Login with admin email OTP (or use ADMIN_TOKEN directly via API)

# Set terminal layout
# Left 60%: terminal
# Right 40%: browser at http://localhost:3000 → Audit Log page
```

---

## The Opening (60 seconds)

> "Before I show you anything, one question: when one of your AI agents takes an action
> — calls an API, reads a record, sends data — how do you know it was authorized?
> Not assumed. Not hoped. **Proven.**"

*Pause 3 seconds.*

> "In 2024, security researchers at PromptArmor documented an attack against Slack AI.
> An attacker posted a single public message containing hidden instructions. When a victim
> asked Slack AI to summarize their messages, the AI retrieved the attacker's message
> and followed the embedded instruction — rendering a phishing link that exfiltrated
> the victim's API key. No jailbreak. No exploit. The agent did exactly what it was
> designed to do.
>
> What I'm showing you is what happens when your agents run through AIControl.
> Every tool call evaluated before execution. Every decision logged immutably.
> When something steps outside policy — stopped before it happens."

---

## Step 1: Stack and Dashboard (90 seconds)

*Browser: http://localhost:3000 → Overview page*

> "This is the AIControl React dashboard. What you're seeing is live — these are real
> intercepts from the warm-up run I did before you joined."

*Point to stat cards:*
- Intercepts today: [N]
- Deny rate: [N%]
- Pending reviews: [N]

> "Every number here is backed by an immutable audit event. Not a metric calculated
> from a log — an append-only record written at the moment of intercept."

---

## Step 2: Run the Lending Demo — Calls 1-3 (90 seconds)

*Terminal:*
```bash
source .env
docker compose exec api python scripts/demos/run_demo.py \
  --scenario lending --token "$DEMO_TOKEN_LENDING" --mode walkthrough
```

**Call 1 — allow:**
> "Credit bureau query. Specific applicant ID, scoped request. **Allow.** Watch the
> dashboard — audit event written immediately. Agent name, tool, parameters, session,
> timestamp. This is your evidence trail building in real time."

*Browser: switch to Audit Log — row appears*

**Call 2 — allow:**
> "Risk model. Internal computation, approved tool. **Allow.** Two rows. Full
> parameters visible — applicant ID, loan amount, model version."

**Call 3 — allow:**
> "Second credit bureau query for the next application in the queue. Legitimate work.
> The agent is processing its normal workload. **Allow.** Three calls, three clean rows."

---

## Step 3: Rate-Limit Denial — Call 4 (90 seconds)

*Press ENTER for call 4:*

**Call 4 — deny (rate limit):**

*Terminal shows: `✗ DECISION: DENY [V2: RATE_LIMIT]`*

*Stop. Pause 2 seconds.*

> "**Blocked.** Same tool. Same agent. Same legitimate request format — a real applicant ID,
> a scoped query. But this is the fourth credit bureau call in this session. Our policy
> allows three. Call four is denied."

*Click the deny row in Audit Log — detail panel opens*

> "Look at what's recorded: the policy that fired is `deny_credit_bureau_rate_limit`.
> The reason is rate limit exceeded — 3 of 3 calls used. The agent identity, the
> session, the exact parameters, the millisecond timestamp. All of it immutable.
>
> Why does this matter? Because the attack that gets past your network security isn't
> a wildcard query. It's an attacker who has compromised an agent token and is calling
> your credit bureau API once, twice, three times — each call looks completely legitimate.
> The rate control catches the pattern the individual call can't."

---

## Step 4: Approved-Tools Denial — Call 5 (60 seconds)

*Press ENTER for call 5:*

**Call 5 — deny (approved_tools):**

*Terminal shows: `✗ DECISION: DENY [V2: APPROVED_TOOLS]`*

> "**Blocked again.** Different reason. This tool — `export_credit_report` — is not
> in this agent's approved tool list. The agent can query credit data. It is not
> authorized to export it to external storage. Those are different authorizations.
> AIControl enforces the boundary."

*Click the deny row:*

> "Reason: tool not in approved_tools. The agent's approved list is: query_credit_bureau,
> run_risk_model, get_income_verification, get_employment_history, approve_loan, deny_loan.
> Export is not on it. If you add it — deliberately, through the dashboard — the next
> call will be allowed. This is your per-agent, per-tool authorization model."

---

## Step 5: Enterprise — Drift Warning (60 seconds)

*Browser: navigate to Governance → Warnings (enterprise feature)*

> "This is policy drift detection — an enterprise feature. Our drift scanner runs
> periodically and checks for governance gaps."

*Point to the warning row: `deny_credit_report_batch_export`*

> "This policy references a tool called `query_credit_report_batch`. But that tool
> doesn't exist in any agent's approved list — it was renamed to `query_credit_bureau`
> at some point and the policy was never updated. The policy rule is dead. It's not
> protecting anything.
>
> Without this detection, you wouldn't know. The policy looks active. It's in your
> policy list. Your auditor sees it. But it's not enforcing anything because no agent
> can ever call that tool anymore. That's a governance gap — AIControl surfaces it."

---

## Step 6: Enterprise — Compliance Report (60 seconds)

*Browser: navigate to Reports*

> "One more thing. Your auditor asks for evidence of AI governance. Today you send
> them a spreadsheet or a PDF you assembled manually. Here's what that looks like
> with AIControl."

*Click Generate Report → select SOC 2 + GLBA → date range last 30 days → Generate*

> "This is an AI-generated compliance report. It maps every policy — active and
> triggered — to the specific regulatory controls they satisfy. It includes the audit
> event counts, the deny rate, the HITL review summary. Everything your examiner needs
> to verify that your AI agents are governed."

*PDF downloads*

> "One click. That's what your next OCC examination looks like."

---

## Closing (30 seconds)

> "Three things happened in the last ten minutes. Your agent was caught at a rate
> limit before it could extract bulk data. It was blocked from a tool it was never
> authorized to use. A stale governance rule was surfaced before your auditor found
> it first.
>
> None of that required a deployment. None of that required modifying your agents.
> One API call in the tool execution path. The rest is configuration.
>
> What's your timeline for your next OCC examination?"

---

## Pre-Demo Checklist (run 15 minutes before)

```bash
# 1. Confirm stack healthy
curl -s http://localhost:8001/health | python3 -m json.tool
# Expected: opa_status: healthy

# 2. Reset + reseed for clean audit log
docker compose exec api python scripts/demo_reset.py
docker compose exec api python scripts/seed.py

# 3. Warm up audit log with fast run (dashboard shows data when prospect joins)
source .env
docker compose exec api python scripts/demos/run_demo.py \
  --scenario lending --token "$DEMO_TOKEN_LENDING" --mode fast

# 4. Dashboard: navigate to Audit Log, clear filters
# 5. Confirm enterprise features visible (AICONTROL_LICENSE_KEY set, VITE_ENTERPRISE=true)
# 6. Browser: two tabs — Overview (tab 1), Audit Log (tab 2)
# 7. Terminal: clean, full width, font size 16+
```

---

## If Questions Come Up Mid-Demo

**"Why not just use database permissions?"**
> "Database permissions control what the service account can access. AIControl controls
> what this specific agent, in this specific session, is authorized to do. 'This agent
> may not call credit bureau more than 3 times per session' is a business policy.
> You cannot express that in a database permission."

**"What's the performance overhead?"**
> "Under 10ms. The duration is in every row of the audit log — you can see it right there."

**"How long does integration take?"**
> "One API call added to your tool execution path. Most teams are running in a day.
> We have copy-paste wrappers for LangChain, CrewAI, OpenAI Agents SDK, and MCP."

**"Can we create a policy live?"**
> *Go to Policies → New Policy. Fill in name, select rule_type, paste condition JSON,
> click Create. It pushes to OPA immediately — no restart.*
> "Policy changes don't require a deployment."
