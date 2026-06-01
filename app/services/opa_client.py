"""Async OPA client — evaluates tool calls against loaded policies."""
import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("opa_client")


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
) -> dict[str, str]:
    """
    Send tool call context to OPA and return the decision.

    Returns dict with keys: decision, reason, fired_policy_id, fired_policy_name

    If OPA is unreachable, behavior is governed by settings.opa_failure_mode:
      "deny"  — fail-closed: deny the tool call (default, safe)
      "allow" — fail-open: allow the tool call (use only in dev/low-risk)
    """
    payload = {
        "input": {
            "tool_name": tool_name,
            "tool_parameters": tool_parameters,
            "policies": policies,
            "current_time": _current_time_context(),
            "call_counts": call_counts if call_counts is not None else {},
        }
    }
    try:
        opa_endpoint = f"{settings.opa_url}/v1/data/aicontrol"
        async with httpx.AsyncClient() as client:
            response = await client.post(opa_endpoint, json=payload)
            response.raise_for_status()
        result = response.json().get("result", {})
        decision = result.get("decision", "allow")
        logger.info("opa_evaluated", tool_name=tool_name, decision=decision)
        return {
            "decision": decision,
            "reason": result.get("reason", "default_allow"),
            "fired_policy_id": result.get("fired_policy_id", ""),
            "fired_policy_name": result.get("fired_policy_name", ""),
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
            return {"decision": "deny", "reason": "opa_unavailable", "fired_policy_id": "", "fired_policy_name": ""}
        else:
            return {"decision": "allow", "reason": "opa_unavailable_fail_open", "fired_policy_id": "", "fired_policy_name": ""}
