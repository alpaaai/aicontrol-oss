# AIControl — Workato Forward Deployment Engineering Walkthrough

<!-- For: Workato Senior Director of Forward Deployment Engineering -->
<!-- Stack: docker compose up -d (postgres + opa), API + MCP gateway via
     bin/start-dev.sh, AICONTROL_LICENSE_KEY=business for enterprise features -->
<!-- One command runs everything: bash scripts/demos/workato_demo.sh [fast|walkthrough] -->

---

## Setup (before the call — 5 minutes)

```bash
# Infra
docker compose up -d

# App (API :8001, MCP Native Proxy :8002, dashboard :3000, three fixture
# MCP servers :8901/:8902/:8903) — foreground, one terminal
bash bin/start-dev.sh

# In a second terminal, set the scanner binary paths (see "Environment"
# below for what to add permanently to .env) and clean-run the whole demo
export SKILL_SCANNER_BINARY_PATH=~/scanner-venvs/skill-scanner/bin/skill-scanner
export MCP_SCANNER_BINARY_PATH=~/scanner-venvs/mcp-scanner/bin/mcp-scanner
export PROMPTFOO_BINARY_PATH=/home/linuxbrew/.linuxbrew/bin/promptfoo
export AICONTROL_LICENSE_KEY=business
bash scripts/demos/workato_demo.sh walkthrough
```

`walkthrough` mode pauses on ENTER between steps so you control pacing live.
Run it once in `fast` mode beforehand to pre-warm the dashboard so it isn't
empty when the call starts, then `demo_reset.py` runs again automatically
at the top of the real `walkthrough` run — the audience never sees stale
data.

Browser: two tabs — Overview (tab 1), Audit Log (tab 2), Admission Scans
(tab 3) at `http://localhost:3000`.

---

## The Opening (60 seconds)

> "You build forward-deployed integrations that give an agent real tool
> access into a customer's systems. The question that follows every one of
> those deployments is: once the agent can call a tool, what actually stops
> it from calling the wrong one — or the right one with the wrong
> arguments? Today I want to show you the layer that answers that, and
> where it sits relative to your own integration surface."

> "It's one API call in the tool-execution path. Every call goes through
> before it executes, gets evaluated against policy, gets logged whether
> it's allowed or not. I'll show you four things: the policy engine itself,
> what happens before a tool or an MCP server is ever trusted, what happens
> at runtime in front of MCP traffic specifically, and how you get evidence
> out the other end."

---

## Integration mechanics (90 seconds — the FDE-specific part)

*Terminal: point at `sdk/src/aicontrol_sdk/adapters/`*

> "This is the part that matters for you: how does this actually wire into
> an agent runtime? We ship adapters for LangGraph, CrewAI, the OpenAI
> Agents SDK, Google ADK, and the Anthropic Agent SDK — one per orchestration
> framework, because each one intercepts tool calls differently."

> "Two are a single global monkeypatch — `patch()` catches every tool call
> a process makes, no per-call wiring. LangGraph and CrewAI don't have that
> kind of global hook, so those adapters attach per-invocation: LangGraph
> via `graph.invoke(config={'callbacks': [...]})`, CrewAI via
> `crewai.hooks.register_before_tool_call_hook`. Same contract everywhere —
> call `client.intercept()` before the tool runs, block if the decision
> isn't allow — just a different attachment point per framework's own
> extension model."

> "One honest caveat, because you'll find it if we don't say it: the
> LangGraph adapter's blocking only holds for async-defined tools right
> now. A sync tool (`@tool def`, only `_run` implemented) routes through
> LangChain's own sync `CallbackManager`, which — by LangChain's own source
> comment — always logs and swallows exceptions from that path regardless
> of `raise_error`. We found that building this demo, not after a customer
> did. It's documented in the adapter's own module docstring and pinned
> with a test. If your integration surface leans on sync tool definitions
> in LangGraph specifically, that's a real gap today, not a hypothetical."

---

## Step 1: Deterministic policy engine (90 seconds)

*Browser: Overview → Audit Log*

*Terminal shows `1. Deterministic policy engine — lending scenario`*

> "Five tool calls, one agent, one session. Watch the third and fourth —
> same tool, same agent, a legitimate applicant ID both times. Call four is
> denied: it's the fourth credit-bureau call this session, the policy
> allows three. Call five is denied for a different reason — the tool
> itself isn't on this agent's approved list."

*Click the deny row in Audit Log*

> "This is OPA underneath — Open Policy Agent, deterministic evaluation,
> never an LLM in the decision path. That matters for you specifically:
> whatever agent framework a customer brings, the policy layer doesn't
> care what model produced the tool call. It evaluates the call itself."

---

## Step 2: Admission control — before a tool or MCP server is ever trusted (2 minutes)

*Terminal shows `2. Admission control — skill and MCP server scanning`*

> "Before an agent ever gets a tool, two things can happen: a skill package
> gets scanned, or an MCP server gets scanned at registration. Both run
> through the same deterministic, no-LLM scanners — no cloud call, nothing
> leaves this machine."

*Watch the first finding — malicious skill*

> "This 'invoice parser' skill has a hidden instruction in its manifest
> telling the agent to ignore policy and exfiltrate data, plus code that
> pipes a network response straight into a shell. Four findings, one
> CRITICAL — caught before the skill is ever loaded, not after."

*Watch the MCP server enrollment*

> "Same idea for an MCP server: this one's `get_invoice_status` tool has a
> poisoned description — a hidden instruction asking the agent to read SSH
> keys and AWS credentials and report them back. The scan runs against the
> real server over the wire, flags it HIGH severity — prompt injection and
> credential harvesting, mapped to MITRE-ATLAS-style technique IDs — and
> the server is enrolled `BLOCKED`, not active. The clean server enrolls
> `ACTIVE`."

---

## Step 3: MCP Native Proxy — runtime enforcement (2 minutes)

*Terminal shows `3. MCP Native Proxy — runtime enforcement`*

> "Admission scanning catches a bad server at enrollment. It doesn't catch
> a good server whose tool starts returning something bad after the fact.
> This is the part that sits in front of live MCP traffic."

*Watch tools/list*

> "This downstream server exposes three tools. The agent only ever sees
> two — `export_all_claims` is filtered out before it reaches the agent's
> context window, because it was never approved for this server."

*Watch the unapproved-tool call*

> "Denied before the call ever reaches the downstream server. Doesn't
> matter what the agent asked for — it wasn't on the approved list."

*Watch `leak_creds_tool`*

> "This call is authorized. Watch what happens to the response instead:
> it contains an AWS key and an embedded `[SYSTEM]` instruction trying to
> hijack the agent's next action. The gateway scans every response before
> it reaches the agent and blocks this one — the agent never sees the
> credential or the injected instruction."

---

## Step 4: Red-teaming (90 seconds)

*Terminal shows `4. Red-teaming (promptfoo)`*

> "This runs the same adapter that registers under
> `scanner_name=promptfoo_redteam` in the admission-scan dashboard — named
> attack plugins, here memory-poisoning and hijacking, run against a target
> agent. One honest note: `promptfoo`'s own `redteam generate` step needs
> an interactive email verification on first use with no headless bypass —
> so today's run mocks only that one subprocess boundary. Everything after
> it — the adapter's generate/eval chaining, JSON parsing, finding
> construction — runs unmocked, and in production this hits the real
> `promptfoo` CLI end to end."

---

## Step 5: Evidence — SIEM export and compliance mapping (90 seconds)

*Terminal shows `5. Outbound SIEM export`*

> "Every audit event can also fire outbound — webhook or OTel collector,
> fire-and-forget, same pattern as our Slack human-review notifications.
> Delivered event, then a failed delivery to show the checkpoint doesn't
> silently advance and drop the event."

*Browser: Reports → Generate Report → select NIST AI RMF + EU AI Act → Generate*

> "And the compliance side: every policy is mapped to the specific
> regulatory controls it satisfies — NIST AI RMF functions, EU AI Act
> article numbers. One click, and that's what your next AI-governance
> review looks like instead of a hand-built spreadsheet."

---

## Closing (30 seconds)

> "Everything you just saw ran through one API call in the tool-execution
> path — the SDK adapters wire that call into whatever framework a
> customer's agents already run on. None of it required changing the
> agent's own logic. What's your integration surface look like today —
> where would this call actually sit for you?"

---

## Environment (add to `.env`, not committed here)

```
SKILL_SCANNER_BINARY_PATH=/home/<you>/scanner-venvs/skill-scanner/bin/skill-scanner
MCP_SCANNER_BINARY_PATH=/home/<you>/scanner-venvs/mcp-scanner/bin/mcp-scanner
PROMPTFOO_BINARY_PATH=/home/linuxbrew/.linuxbrew/bin/promptfoo
```

Scanner binaries are provisioned with `scripts/provision_skill_scanner_venv.sh`
and `scripts/provision_mcp_scanner_venv.sh` — pass `SKILL_SCANNER_VENV_DIR`
/ `MCP_SCANNER_VENV_DIR` pointing outside `/opt` and outside the repo (both
are commonly permission-restricted) if the defaults don't work in your
environment, e.g. `~/scanner-venvs/...`.

---

## If Questions Come Up Mid-Demo

**"How does this compare to a plain allowlist on the MCP gateway itself?"**
> "An allowlist tells you what's permitted. It doesn't scan a tool's
> description for a hidden instruction, or a response for an embedded
> credential. Those are the two failure modes admission scanning and the
> response scanner catch that a static allowlist structurally can't."

**"What's the performance overhead on the runtime path?"**
> "Under 10ms for the policy evaluation itself — duration is in every audit
> row. Response scanning on the MCP gateway path adds a regex/YARA pass
> over the response text, not a network call."

**"Can we author a policy live?"**
> *Dashboard → Policies → New Policy, or describe it in plain English via
> the NL policy authoring flow — the LLM proposes a candidate restricted to
> the same closed set of rule types OPA already evaluates, inert until a
> human explicitly approves it.*

**"What if we're not using MCP at all yet?"**
> "The policy engine and the SDK adapters don't require MCP — they intercept
> tool calls directly inside LangGraph/CrewAI/OpenAI Agents SDK/Google ADK/
> Anthropic Agent SDK. MCP-specific scanning and the runtime proxy are an
> additional layer for when tools come from a server you don't control."
