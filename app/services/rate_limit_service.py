"""Rate-limit COUNT queries for P1-2 policy enforcement."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.wal import count_unshipped_for_session_tool, default_wal_writer

WINDOW_INTERVALS: dict[str, timedelta] = {
    "5m":  timedelta(minutes=5),
    "60m": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d":  timedelta(days=7),
}


async def count_tool_calls_in_window(
    db: AsyncSession,
    agent_id: str,
    session_id: str,
    tool_name: str,
    window: str,
) -> int:
    """
    Count prior audit_events rows for this tool in the given window.
    Count reflects calls already written — current call is not yet included.
    Raises KeyError for unrecognised non-session window strings.
    """
    if window == "session":
        result = await db.execute(
            text(
                "SELECT COUNT(*) FROM audit_events "
                "WHERE session_id = :session_id AND tool_name = :tool_name"
            ),
            {"session_id": session_id, "tool_name": tool_name},
        )
        postgres_count = result.scalar_one()
        pending_count = count_unshipped_for_session_tool(
            default_wal_writer.wal_path, session_id, tool_name
        )
        return postgres_count + pending_count
    else:
        since = datetime.now(timezone.utc) - WINDOW_INTERVALS[window]
        result = await db.execute(
            text(
                "SELECT COUNT(*) FROM audit_events "
                "WHERE agent_id = :agent_id "
                "AND tool_name = :tool_name "
                "AND created_at >= :since"
            ),
            {"agent_id": agent_id, "tool_name": tool_name, "since": since},
        )
    return result.scalar_one()


async def build_call_counts(
    db: AsyncSession,
    agent_id: str,
    session_id: str,
    tool_name: str,
    active_policies: list[dict],
) -> dict[str, int]:
    """
    For each active rate_limit policy whose tools list contains tool_name,
    run COUNT query. Returns {tool_name: count}.
    Each tool is queried at most once even if multiple policies target it.
    Returns empty dict if no rate_limit policies match this tool.
    """
    counts: dict[str, int] = {}
    for policy in active_policies:
        if policy.get("rule_type") != "rate_limit":
            continue
        condition = policy.get("condition", {})
        if tool_name not in condition.get("tools", []):
            continue
        if tool_name in counts:
            continue
        window = condition["rate_limit"]["window"]
        counts[tool_name] = await count_tool_calls_in_window(
            db, agent_id, session_id, tool_name, window
        )
    return counts
