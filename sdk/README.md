# aicontrol-sdk

Governance SDK for AIControl. Two ways to instrument an agent:

## `instrument()` — auto-patch a supported framework

```python
import asyncio
from aicontrol_sdk import instrument

async def main():
    await instrument(agent_name="my-agent", url="http://localhost:8001", token="...")
    # every tool call made through the detected framework (Anthropic Claude
    # Agent SDK, OpenAI Agents SDK, or Google ADK) is now intercepted by
    # AIControl before it executes.

asyncio.run(main())
```

`instrument()` auto-registers the agent on first call (`POST /agents/register`) unless
`agent_id=` is passed explicitly. Pass `framework=` to skip auto-detection.

## `@control` — framework-agnostic decorator for any Python callable

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

## Configuration (env vars, read by `Config.from_env()`)

- `AICONTROL_URL` (required)
- `AICONTROL_TOKEN` (required)
- `AICONTROL_AGENT_ID` (optional)
- `AICONTROL_FAIL_MODE` — `allow` or `deny` (default `deny`): behavior when AIControl is unreachable.

## Framework extras

`aicontrol-sdk` isn't published to PyPI yet — install from source with the extra you need:

```bash
pip install "./sdk[anthropic]"   # claude-agent-sdk
pip install "./sdk[openai]"      # openai-agents
pip install "./sdk[google-adk]"  # google-adk
# or: pip install "git+https://github.com/alpaaai/aicontrol-oss#subdirectory=sdk[anthropic]"
```

## Exceptions

- `PolicyDeniedError(reason, policy_name)` — raised on a `deny` decision.
- `ReviewPendingError(review_id)` — raised on a `review` decision.
- `AIControlUnavailableError(cause)` — raised when AIControl is unreachable and `AICONTROL_FAIL_MODE=deny`.
- `UnknownDecisionError(decision)` — raised when AIControl returns a decision value this SDK
  version doesn't recognize (a typo, case mismatch, or a future decision type) — fails
  closed rather than silently treating it as an implicit allow.
