"""Async OPA client — evaluates tool calls against loaded policies."""
import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("opa_client")

# Module-level singleton: a fresh httpx.AsyncClient() per call pays a full TCP
# connection setup on every decision, which alone can exceed the 20ms
# decision-timeout budget under any load. Reuse one pooled client instead —
# same rationale as app.services.wal.default_wal_writer (importable directly,
# no app.state dependency, so ASGITransport-based tests get it too).
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient()
    return _client


async def warmup() -> None:
    """Eagerly establish the persistent client's TCP connection to OPA.
    Call once during app startup, before traffic is accepted. Without this,
    the connection is opened lazily on the first real decision — found via
    a clean-container E2E run, where that first request paid connection
    setup and evaluation inside the same decision-timeout budget and timed
    out, incorrectly fail-closing a legitimate first tool call. Best-effort:
    never raises, since OPA being briefly unreachable at startup shouldn't
    crash the app — the normal per-request fail path covers that case."""
    try:
        client = _get_client()
        await client.get(f"{settings.opa_url}/health", timeout=settings.opa_decision_timeout_s * 10)
        logger.info("opa_client_warmed_up")
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
        logger.warning("opa_client_warmup_failed", error=str(exc))


def _current_time_context() -> dict[str, int]:
    """Return current UTC day-of-week (0=Mon…6=Sun) and hour for temporal policy evaluation."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return {
        "day_of_week": now.weekday(),
        "hour": now.hour,
    }


async def evaluate(
    tool_name: str,
    tool_parameters: dict[str, Any],
    policies: list[dict],
    agent_id: str = "",
    call_counts: dict[str, int] | None = None,
    cumulative_tokens: dict[str, float] | None = None,
    cumulative_cost_usd: dict[str, float] | None = None,
    agent_cumulative_tokens: float = 0,
    agent_cumulative_cost_usd: float = 0,
    org_cumulative_tokens: float = 0,
    org_cumulative_cost_usd: float = 0,
    timeout_s: float | None = None,
) -> dict[str, str]:
    """
    Send tool call context to OPA and return the decision.

    Returns dict with keys: decision, reason, fired_policy_id, fired_policy_name, bypass

    timeout_s defaults to settings.opa_decision_timeout_s (the WS0 hard
    decision-timeout budget — see app/core/config.py for the measured
    latency this is based on). If OPA is unreachable OR exceeds timeout_s,
    behavior is governed by settings.opa_failure_mode:
      "deny"  — fail-closed: deny the tool call (default, safe)
      "allow" — fail-open: allow the tool call (use only in dev/low-risk)
    Either way, bypass=True is returned so the caller can audit + alert.
    """
    timeout_s = timeout_s if timeout_s is not None else settings.opa_decision_timeout_s
    payload = {
        "input": {
            "tool_name": tool_name,
            "tool_parameters": tool_parameters,
            "policies": policies,
            "current_time": _current_time_context(),
            "call_counts": call_counts if call_counts is not None else {},
            "cumulative_tokens": cumulative_tokens if cumulative_tokens is not None else {},
            "cumulative_cost_usd": cumulative_cost_usd if cumulative_cost_usd is not None else {},
            "agent_cumulative_tokens": agent_cumulative_tokens,
            "agent_cumulative_cost_usd": agent_cumulative_cost_usd,
            "org_cumulative_tokens": org_cumulative_tokens,
            "org_cumulative_cost_usd": org_cumulative_cost_usd,
        }
    }
    try:
        opa_endpoint = f"{settings.opa_url}/v1/data/aicontrol"
        client = _get_client()
        response = await client.post(opa_endpoint, json=payload, timeout=timeout_s)
        response.raise_for_status()
        result = response.json().get("result", {})
        decision = result.get("decision", "allow")
        logger.info("opa_evaluated", tool_name=tool_name, decision=decision)
        return {
            "decision": decision,
            "reason": result.get("reason", "default_allow"),
            "fired_policy_id": result.get("fired_policy_id", ""),
            "fired_policy_name": result.get("fired_policy_name", ""),
            "bypass": False,
        }
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
        logger.error(
            "opa_evaluation_failed",
            error=str(exc),
            failure_mode=settings.opa_failure_mode,
            tool_name=tool_name,
            agent_id=agent_id,
        )
        if settings.opa_failure_mode == "deny":
            return {"decision": "deny", "reason": "opa_unavailable", "fired_policy_id": "", "fired_policy_name": "", "bypass": True}
        else:
            return {"decision": "allow", "reason": "opa_unavailable_fail_open", "fired_policy_id": "", "fired_policy_name": "", "bypass": True}
