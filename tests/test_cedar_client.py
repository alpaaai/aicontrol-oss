"""Cedar in-process evaluation, including the three-valued decision.

The cedar_text below is hand-written rather than produced by policy_compiler, so
its thresholds carry the NUMERIC_SCALE factor explicitly. Cedar has no float type
and rejects a request outright if it sees one, so cedar_client scales every
context number to an integer; a policy literal that skipped the same scaling
would compare against a number a million times too small.
"""
import pytest

from app.services.cedar_client import evaluate
from app.services.policy_compiler import NUMERIC_SCALE

DENY_POLICY = {
    "id": "11111111-1111-1111-1111-111111111111",
    "name": "deny_bulk_claims_query",
    "effect": "deny",
    "cedar_text": (
        '@id("11111111-1111-1111-1111-111111111111") @effect("deny")\n'
        'forbid (principal == Agent::"claims-adjuster", action == Action::"db_query", '
        'resource == System::"guidewire")\n'
        f"when {{ context.row_limit > {100 * NUMERIC_SCALE} }};"
    ),
}

REVIEW_POLICY = {
    "id": "22222222-2222-2222-2222-222222222222",
    "name": "review_high_value_payment",
    "effect": "review",
    "cedar_text": (
        '@id("22222222-2222-2222-2222-222222222222") @effect("review")\n'
        'forbid (principal == Agent::"claims-adjuster", action == Action::"release_payment", '
        'resource == System::"guidewire")\n'
        f"when {{ context.amount > {50000 * NUMERIC_SCALE} }};"
    ),
}


@pytest.mark.asyncio
async def test_no_policy_matches_returns_allow():
    result = await evaluate(
        agent_name="claims-adjuster", agent_groups=[], tool_name="release_payment",
        system="guidewire", context={"amount": 100, "row_limit": 1},
        policies=[DENY_POLICY, REVIEW_POLICY],
    )
    assert result["decision"] == "allow"
    assert result["fired_policy_id"] is None


@pytest.mark.asyncio
async def test_review_policy_yields_review_not_deny():
    result = await evaluate(
        agent_name="claims-adjuster", agent_groups=[], tool_name="release_payment",
        system="guidewire", context={"amount": 90000, "row_limit": 1},
        policies=[DENY_POLICY, REVIEW_POLICY],
    )
    assert result["decision"] == "review"
    assert result["fired_policy_id"] == REVIEW_POLICY["id"]
    assert result["fired_policy_name"] == "review_high_value_payment"


@pytest.mark.asyncio
async def test_deny_policy_yields_deny():
    result = await evaluate(
        agent_name="claims-adjuster", agent_groups=[], tool_name="db_query",
        system="guidewire", context={"row_limit": 5000},
        policies=[DENY_POLICY, REVIEW_POLICY],
    )
    assert result["decision"] == "deny"
    assert result["fired_policy_id"] == DENY_POLICY["id"]


@pytest.mark.asyncio
async def test_deny_wins_when_deny_and_review_both_match():
    both = dict(REVIEW_POLICY)
    both = {
        "id": "33333333-3333-3333-3333-333333333333",
        "name": "deny_same_call",
        "effect": "deny",
        "cedar_text": (
            '@id("33333333-3333-3333-3333-333333333333") @effect("deny")\n'
            'forbid (principal == Agent::"claims-adjuster", action == Action::"release_payment", '
            'resource == System::"guidewire")\n'
            f"when {{ context.amount > {10000 * NUMERIC_SCALE} }};"
        ),
    }
    result = await evaluate(
        agent_name="claims-adjuster", agent_groups=[], tool_name="release_payment",
        system="guidewire", context={"amount": 90000},
        policies=[REVIEW_POLICY, both],
    )
    assert result["decision"] == "deny"


@pytest.mark.asyncio
async def test_agent_group_membership_matches_group_scoped_policy():
    group_policy = {
        "id": "44444444-4444-4444-4444-444444444444",
        "name": "finance_group_deny",
        "effect": "deny",
        "cedar_text": (
            '@id("44444444-4444-4444-4444-444444444444") @effect("deny")\n'
            'forbid (principal in AgentGroup::"finance", action == Action::"wire_transfer", '
            "resource);"
        ),
    }
    result = await evaluate(
        agent_name="ap-clerk", agent_groups=["finance"], tool_name="wire_transfer",
        system="netsuite", context={}, policies=[group_policy],
    )
    assert result["decision"] == "deny"


@pytest.mark.asyncio
async def test_malformed_cedar_fails_closed():
    broken = {
        "id": "55555555-5555-5555-5555-555555555555",
        "name": "broken",
        "effect": "deny",
        "cedar_text": "forbid (this is not cedar",
    }
    result = await evaluate(
        agent_name="a", agent_groups=[], tool_name="t", system="unknown",
        context={}, policies=[broken],
    )
    assert result["decision"] == "deny"
    assert "evaluation_error" in result["reason"]


@pytest.mark.asyncio
async def test_policy_set_is_cached_and_reused():
    """Pre-parsing is what keeps evaluation inside the decision budget (spike:
    p99 0.243ms pre-parsed vs 1.989ms parsing every call), so the same policy
    source must not re-parse."""
    from app.services import cedar_client

    cedar_client.invalidate_policy_set_cache()
    assert cedar_client._policy_set_cache == {}

    kwargs = dict(
        agent_name="claims-adjuster", agent_groups=[], tool_name="release_payment",
        system="guidewire", context={"amount": 1, "row_limit": 1},
        policies=[DENY_POLICY, REVIEW_POLICY],
    )
    await evaluate(**kwargs)
    assert len(cedar_client._policy_set_cache) == 1
    first = next(iter(cedar_client._policy_set_cache.values()))

    await evaluate(**kwargs)
    assert len(cedar_client._policy_set_cache) == 1
    assert next(iter(cedar_client._policy_set_cache.values())) is first


@pytest.mark.asyncio
async def test_editing_a_policy_yields_a_new_cache_entry():
    """The cache key is a hash of the policy source, so an edit cannot serve a
    stale PolicySet even if invalidate is never called."""
    from app.services import cedar_client

    cedar_client.invalidate_policy_set_cache()
    await evaluate(
        agent_name="claims-adjuster", agent_groups=[], tool_name="db_query",
        system="guidewire", context={"row_limit": 1}, policies=[DENY_POLICY],
    )
    edited = dict(DENY_POLICY)
    edited["cedar_text"] = DENY_POLICY["cedar_text"].replace(
        str(100 * NUMERIC_SCALE), str(10 * NUMERIC_SCALE))
    await evaluate(
        agent_name="claims-adjuster", agent_groups=[], tool_name="db_query",
        system="guidewire", context={"row_limit": 1}, policies=[edited],
    )
    assert len(cedar_client._policy_set_cache) == 2

    cedar_client.invalidate_policy_set_cache()
    assert cedar_client._policy_set_cache == {}
