"""Generate 30 days of synthetic sessions/audit_events for the self-service demo environment.

Reuses scripts/seed.py's existing agent list and per-agent tool names (already
scenario-grounded from the demo scripts) — no new tool/agent pairings invented here.
Every row is deterministically UUID'd from (agent, day, session, call) so re-running
this script is a no-op (ON CONFLICT DO NOTHING), and every session is tagged with
DEMO_SYNTHETIC_MARKER so it can be identified and cleaned up independently of real data.
"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.models.database import async_session_factory
from scripts.seed import AGENTS, AGENT_APPROVED_TOOLS

DEMO_SYNTHETIC_MARKER = "demo-synthetic-seed"
DEFAULT_DAYS = 30

# Fixed weighting: mostly allowed traffic, a believable slice of denies/reviews.
_DECISION_THRESHOLDS = (("allow", 0.75), ("deny", 0.90), ("review", 1.0))


def _decide(rng: random.Random) -> str:
    r = rng.random()
    for decision, upper in _DECISION_THRESHOLDS:
        if r < upper:
            return decision
    return "review"


def _deterministic_uuid(*parts: object) -> uuid.UUID:
    name = "|".join(str(p) for p in parts)
    return uuid.uuid5(uuid.NAMESPACE_URL, f"aicontrol-demo-synthetic:{name}")


async def generate_synthetic_data(
    days: int = DEFAULT_DAYS,
    now: datetime | None = None,
    session_factory=async_session_factory,
) -> dict:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    rng = random.Random(42)  # deterministic across reruns -> idempotent
    sessions_written = 0
    events_written = 0

    async with session_factory() as db:
        for agent in AGENTS:
            agent_id = agent["id"]
            tools = AGENT_APPROVED_TOOLS.get(agent_id) or [f"{agent['name']}_default_action"]

            for day_offset in range(days):
                day = now - timedelta(days=day_offset)
                num_sessions = rng.randint(1, 3)

                for s_idx in range(num_sessions):
                    session_id = _deterministic_uuid(agent_id, day_offset, s_idx)
                    started_at = day - timedelta(
                        hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
                    )
                    completed_at = started_at + timedelta(minutes=rng.randint(1, 15))

                    await db.execute(
                        text(
                            "INSERT INTO sessions "
                            "(id, agent_id, trigger_context, status, started_at, completed_at) "
                            "VALUES (:id, :agent_id, :trigger_context, 'completed', "
                            ":started_at, :completed_at) "
                            "ON CONFLICT (id) DO NOTHING"
                        ),
                        {
                            "id": str(session_id),
                            "agent_id": agent_id,
                            "trigger_context": DEMO_SYNTHETIC_MARKER,
                            "started_at": started_at,
                            "completed_at": completed_at,
                        },
                    )
                    sessions_written += 1

                    num_calls = rng.randint(1, 4)
                    for seq in range(1, num_calls + 1):
                        tool_name = rng.choice(tools)
                        decision = _decide(rng)
                        event_id = _deterministic_uuid(agent_id, day_offset, s_idx, seq)
                        created_at = started_at + timedelta(seconds=seq * 5)
                        reason = None if decision == "allow" else f"synthetic demo {decision}"

                        await db.execute(
                            text(
                                "INSERT INTO audit_events "
                                "(id, session_id, sequence_number, agent_id, agent_name, "
                                " tool_name, tool_parameters, decision, decision_reason, "
                                " created_at) "
                                "VALUES (:id, :session_id, :sequence_number, :agent_id, "
                                ":agent_name, :tool_name, CAST(:tool_parameters AS jsonb), "
                                ":decision, :decision_reason, :created_at) "
                                "ON CONFLICT (id) DO NOTHING"
                            ),
                            {
                                "id": str(event_id),
                                "session_id": str(session_id),
                                "sequence_number": seq,
                                "agent_id": agent_id,
                                "agent_name": agent["name"],
                                "tool_name": tool_name,
                                "tool_parameters": "{}",
                                "decision": decision,
                                "decision_reason": reason,
                                "created_at": created_at,
                            },
                        )
                        events_written += 1

        await db.commit()

    return {"sessions_written": sessions_written, "events_written": events_written}


async def main() -> None:
    result = await generate_synthetic_data()
    print(
        f"Synthetic demo data: {result['sessions_written']} sessions, "
        f"{result['events_written']} audit events (30-day window)."
    )


if __name__ == "__main__":
    asyncio.run(main())
