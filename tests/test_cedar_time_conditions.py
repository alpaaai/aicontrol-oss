"""time_conditions enforcement, compiled and evaluated in-process.

Replaces the five temporal tests in test_policy_engine, which POSTed a policy to
the shared live server and then asserted an /intercept decision -- order-dependent
once enough prior files had run. Nothing here touches the server or the database,
and the hour and day are passed explicitly rather than mocked, so these hold in
any run order and at any wall-clock time.

Mirrors base.rego's policy_time_violation: deny_days alone or deny_hours alone
each determines the violation; when both are given they are ANDed, which base.rego
was deliberately changed from OR to AND so that a policy meaning "weekends, 9-5"
does not deny all day Saturday and 9-5 on every weekday.
"""
import uuid

import pytest

from app.models.schemas import Policy
from app.services.cedar_client import evaluate, invalidate_policy_set_cache
from app.services.policy_compiler import compile_policy

TOOL = "deploy_to_production"
SATURDAY, SUNDAY, WEDNESDAY = 5, 6, 2


async def _decide(time_conditions: dict, *, day: int, hour: int) -> str:
    row = Policy(
        id=uuid.uuid4(),
        name="temporal_probe",
        condition={"time_conditions": time_conditions},
        principal_type=None,
        principal_id=None,
        action_tool=TOOL,
        resource_system=None,
        effect="deny",
    )
    invalidate_policy_set_cache()
    result = await evaluate(
        agent_name="release-agent",
        agent_groups=[],
        tool_name=TOOL,
        system="unknown",
        context={"tool_name": TOOL, "day_of_week": day, "hour": hour},
        policies=[{
            "id": str(row.id), "name": row.name, "effect": "deny",
            "cedar_text": compile_policy(row),
        }],
    )
    return result["decision"]


# ── deny_days alone ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("day", [SATURDAY, SUNDAY])
async def test_deny_days_denies_on_listed_days(day):
    assert await _decide({"deny_days": [5, 6]}, day=day, hour=12) == "deny"


@pytest.mark.asyncio
async def test_deny_days_allows_on_unlisted_days():
    assert await _decide({"deny_days": [5, 6]}, day=WEDNESDAY, hour=12) == "allow"


# ── deny_hours alone ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deny_hours_denies_inside_the_window():
    assert await _decide({"deny_hours": {"from": 9, "to": 17}}, day=WEDNESDAY, hour=12) == "deny"


@pytest.mark.asyncio
async def test_deny_hours_is_inclusive_of_from():
    assert await _decide({"deny_hours": {"from": 9, "to": 17}}, day=WEDNESDAY, hour=9) == "deny"


@pytest.mark.asyncio
async def test_deny_hours_is_exclusive_of_to():
    """17:00 is outside a 9-to-17 window: base.rego compares hour < to."""
    assert await _decide({"deny_hours": {"from": 9, "to": 17}}, day=WEDNESDAY, hour=17) == "allow"


@pytest.mark.asyncio
async def test_deny_hours_allows_outside_the_window():
    assert await _decide({"deny_hours": {"from": 9, "to": 17}}, day=WEDNESDAY, hour=3) == "allow"


# ── both together are ANDed ───────────────────────────────────────────────────

BOTH = {"deny_days": [5, 6], "deny_hours": {"from": 9, "to": 17}}


@pytest.mark.asyncio
async def test_both_denies_only_when_day_and_hour_match():
    assert await _decide(BOTH, day=SATURDAY, hour=12) == "deny"


@pytest.mark.asyncio
async def test_both_allows_when_only_the_day_matches():
    """The bug base.rego was fixed for: an OR here would deny all day Saturday."""
    assert await _decide(BOTH, day=SATURDAY, hour=3) == "allow"


@pytest.mark.asyncio
async def test_both_allows_when_only_the_hour_matches():
    """And an OR would deny 9-5 on every weekday."""
    assert await _decide(BOTH, day=WEDNESDAY, hour=12) == "allow"


# ── the outside-window form used by the C4 table ──────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("hour,expected", [(3, "deny"), (22, "deny"), (12, "allow")])
async def test_hours_window_denies_outside_the_range(hour, expected):
    assert await _decide({"hours": [6, 20]}, day=WEDNESDAY, hour=hour) == expected
