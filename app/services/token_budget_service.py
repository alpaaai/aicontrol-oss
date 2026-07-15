"""Cumulative token/cost SUM queries for WS3 token_budget policy enforcement.
Mirrors app/services/rate_limit_service.py's build_call_counts exactly, one
level up (SUM instead of COUNT, two dimensions instead of one)."""
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rate_limit_service import WINDOW_INTERVALS
from app.services.wal import default_wal_writer, sum_unshipped_for_session_tool


async def _sum_in_window(
    db: AsyncSession, column: str, agent_id: str, session_id: str, tool_name: str, window: str,
) -> float:
    if window == "session":
        result = await db.execute(
            text(f"SELECT COALESCE(SUM({column}), 0) FROM audit_events WHERE session_id = :session_id AND tool_name = :tool_name"),
            {"session_id": session_id, "tool_name": tool_name},
        )
        postgres_sum = float(result.scalar_one())
        pending_tokens, pending_cost = sum_unshipped_for_session_tool(
            default_wal_writer.wal_path, session_id, tool_name
        )
        pending = pending_tokens if "input_tokens" in column else pending_cost
        return postgres_sum + pending
    else:
        since = datetime.now(timezone.utc) - WINDOW_INTERVALS[window]
        result = await db.execute(
            text(f"SELECT COALESCE(SUM({column}), 0) FROM audit_events WHERE agent_id = :agent_id AND tool_name = :tool_name AND created_at >= :since"),
            {"agent_id": agent_id, "tool_name": tool_name, "since": since},
        )
    return float(result.scalar_one())


async def build_token_budgets(
    db: AsyncSession, agent_id: str, session_id: str, tool_name: str, active_policies: list[dict],
) -> tuple[dict[str, float], dict[str, float]]:
    """For each active tool_denylist policy with a token_budget condition
    targeting tool_name, sum prior input_tokens+output_tokens and prior
    cost_usd. Returns (cumulative_tokens, cumulative_cost_usd), each
    {tool_name: sum}. Empty dicts if no token_budget policy matches."""
    cumulative_tokens: dict[str, float] = {}
    cumulative_cost_usd: dict[str, float] = {}

    for policy in active_policies:
        if policy.get("rule_type") != "tool_denylist":
            continue
        condition = policy.get("condition", {})
        token_budget = condition.get("token_budget")
        if not token_budget or tool_name not in condition.get("blocked_tools", []):
            continue

        window = token_budget["window"]
        if token_budget.get("max_tokens") and tool_name not in cumulative_tokens:
            cumulative_tokens[tool_name] = await _sum_in_window(
                db, "COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)", agent_id, session_id, tool_name, window,
            )
        if token_budget.get("max_cost_usd") and tool_name not in cumulative_cost_usd:
            cumulative_cost_usd[tool_name] = await _sum_in_window(
                db, "COALESCE(cost_usd, 0)", agent_id, session_id, tool_name, window,
            )

    return cumulative_tokens, cumulative_cost_usd


async def build_aggregate_budgets(
    db: AsyncSession, agent_id: str, active_policies: list[dict],
) -> tuple[dict[str, float], dict[str, float]]:
    """Sum tokens/cost across every tool call (no tool_name filter), for
    the standalone rule_type == "budget" policy. Only queries if at least
    one active "budget" policy exists -- avoids the extra SQL round-trip
    on the (overwhelmingly common) case of no aggregate-budget policy."""
    has_budget_policy = any(p.get("rule_type") == "budget" for p in active_policies)
    if not has_budget_policy:
        return {}, {}

    agent_result = await db.execute(
        text("SELECT COALESCE(SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)), 0) AS tokens, "
             "COALESCE(SUM(COALESCE(cost_usd, 0)), 0) AS cost_usd FROM audit_events WHERE agent_id = :agent_id"),
        {"agent_id": agent_id},
    )
    agent_row = agent_result.one()

    org_result = await db.execute(
        text("SELECT COALESCE(SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)), 0) AS tokens, "
             "COALESCE(SUM(COALESCE(cost_usd, 0)), 0) AS cost_usd FROM audit_events")
    )
    org_row = org_result.one()

    return (
        {"tokens": float(agent_row.tokens), "cost_usd": float(agent_row.cost_usd)},
        {"tokens": float(org_row.tokens), "cost_usd": float(org_row.cost_usd)},
    )
