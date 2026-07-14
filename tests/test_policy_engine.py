"""Integration tests for policy engine enhancements — numeric, compound, temporal, alias.

Numeric, compound, and alias tests hit the live API at http://localhost:8001.
Temporal tests use ASGITransport (in-process) so the datetime mock reaches opa_client.
Fixtures are session-scoped; policies created in one test persist to later tests
in the same group by design. Allow-path tests use parameters that do not trigger
any earlier-created policy.
"""
import uuid
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

_TEST_SESSION_ID = str(uuid.uuid4())
_FORBIDDEN_SESSION_ID = "00000000-0000-0000-0000-000000000099"


def test_no_hardcoded_session_id():
    """Guard: _TEST_SESSION_ID must not be the well-known fake UUID that pollutes audit_events."""
    assert _TEST_SESSION_ID != _FORBIDDEN_SESSION_ID


# ── Numeric comparison tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_numeric_gt_deny(client, agent_token, admin_token):
    """Deny when loan_amount exceeds numeric threshold."""
    await client.post("/policies", headers=admin_token, json={
        "name": "test_loan_limit",
        "description": "Deny loans over 500k",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["approve_loan"],
            "numeric_conditions": [
                {"parameter": "loan_amount", "operator": "gt", "value": 500000}
            ]
        },
        "action": "deny", "severity": "high", "active": True,
    })
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000001",
        "agent_name": "claims-processing-agent",
        "tool_name": "approve_loan",
        "tool_parameters": {"loan_amount": 750000, "applicant_id": "APP-001"},
        "sequence_number": 1,
    })
    data = resp.json()
    assert data["decision"] == "deny"
    assert "loan_amount" in data["reason"]


@pytest.mark.asyncio
async def test_numeric_gt_allow_below_threshold(client, agent_token):
    """Allow when loan_amount is below threshold."""
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000001",
        "agent_name": "claims-processing-agent",
        "tool_name": "approve_loan",
        "tool_parameters": {"loan_amount": 200000, "applicant_id": "APP-002"},
        "sequence_number": 2,
    })
    assert resp.json()["decision"] == "allow"


@pytest.mark.asyncio
async def test_numeric_lt_deny(client, agent_token, admin_token):
    """Deny when credit_score is below minimum."""
    await client.post("/policies", headers=admin_token, json={
        "name": "test_credit_floor",
        "description": "Deny if credit score below 600",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["approve_loan"],
            "numeric_conditions": [
                {"parameter": "credit_score", "operator": "lt", "value": 600}
            ]
        },
        "action": "deny", "severity": "high", "active": True,
    })
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000001",
        "agent_name": "claims-processing-agent",
        "tool_name": "approve_loan",
        "tool_parameters": {"loan_amount": 100000, "credit_score": 520},
        "sequence_number": 3,
    })
    assert resp.json()["decision"] == "deny"


@pytest.mark.asyncio
async def test_numeric_multi_condition_deny_both_match(client, agent_token, admin_token):
    """Deny when both numeric conditions in array match."""
    await client.post("/policies", headers=admin_token, json={
        "name": "test_multi_numeric",
        "description": "Deny high amount AND long term",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["approve_loan"],
            "numeric_conditions": [
                {"parameter": "loan_amount", "operator": "gt", "value": 500000},
                {"parameter": "loan_term_years", "operator": "gt", "value": 30}
            ]
        },
        "action": "deny", "severity": "critical", "active": True,
    })
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000001",
        "agent_name": "claims-processing-agent",
        "tool_name": "approve_loan",
        "tool_parameters": {"loan_amount": 750000, "loan_term_years": 35},
        "sequence_number": 4,
    })
    assert resp.json()["decision"] == "deny"


@pytest.mark.asyncio
async def test_numeric_multi_condition_allow_one_fails(client, agent_token):
    """Allow when only one of multiple numeric conditions matches (AND logic).

    Uses loan_amount: 300000 — below the 500k threshold of test_loan_limit —
    so neither test_loan_limit nor test_multi_numeric (which also requires
    loan_amount > 500k) fires.
    """
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000001",
        "agent_name": "claims-processing-agent",
        "tool_name": "approve_loan",
        "tool_parameters": {"loan_amount": 300000, "loan_term_years": 35},
        "sequence_number": 5,
    })
    assert resp.json()["decision"] == "allow"


@pytest.mark.asyncio
async def test_numeric_gt_deny_with_stringified_number(client, agent_token, admin_token):
    """A gt threshold must not falsely deny when the actual value is a LOW number
    sent as a string -- Rego's string>number cross-type ordering currently makes
    any string 'win' regardless of its numeric value."""
    await client.post("/policies", headers=admin_token, json={
        "name": "test_loan_limit_string_low",
        "description": "Deny loans over 500k",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["approve_loan_string_test"],
            "numeric_conditions": [
                {"parameter": "loan_amount", "operator": "gt", "value": 500000}
            ]
        },
        "action": "deny", "severity": "high", "active": True,
    })
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000001",
        "agent_name": "claims-processing-agent",
        "tool_name": "approve_loan_string_test",
        "tool_parameters": {"loan_amount": "99", "applicant_id": "APP-STR-1"},
        "sequence_number": 1,
    })
    assert resp.json()["decision"] == "allow", (
        "a stringified '99' must be treated as 99, not as 'greater than 500000' "
        "just because it's a string"
    )


@pytest.mark.asyncio
async def test_numeric_lt_deny_with_stringified_number(client, agent_token, admin_token):
    """An lt threshold must still fire when the actual value is a low number sent
    as a string -- currently strings never satisfy lt/lte at all."""
    await client.post("/policies", headers=admin_token, json={
        "name": "test_credit_floor_string",
        "description": "Deny if credit score below 600",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["approve_loan_string_test2"],
            "numeric_conditions": [
                {"parameter": "credit_score", "operator": "lt", "value": 600}
            ]
        },
        "action": "deny", "severity": "high", "active": True,
    })
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000001",
        "agent_name": "claims-processing-agent",
        "tool_name": "approve_loan_string_test2",
        "tool_parameters": {"credit_score": "550", "applicant_id": "APP-STR-2"},
        "sequence_number": 1,
    })
    assert resp.json()["decision"] == "deny", (
        "a stringified '550' must be treated as 550 (< 600), not silently allowed"
    )


# ── Compound AND/OR tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compound_all_of_deny_both_match(client, agent_token, admin_token):
    """Deny when ALL conditions in all_of match."""
    await client.post("/policies", headers=admin_token, json={
        "name": "test_compound_and",
        "description": "Deny high-risk subprime loans",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["approve_loan"],
            "all_of": [
                {"numeric_conditions": [{"parameter": "loan_amount", "operator": "gt", "value": 500000}]},
                {"parameter_match": {"applicant_type": "subprime"}}
            ]
        },
        "action": "deny", "severity": "critical", "active": True,
    })
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000001",
        "agent_name": "claims-processing-agent",
        "tool_name": "approve_loan",
        "tool_parameters": {"loan_amount": 750000, "applicant_type": "subprime"},
        "sequence_number": 1,
    })
    assert resp.json()["decision"] == "deny"


@pytest.mark.asyncio
async def test_compound_all_of_allow_partial_match(client, agent_token):
    """Allow when only one condition in all_of matches.

    Uses loan_amount: 300000 — below the 500k threshold of test_loan_limit and
    test_compound_and — so neither fires.
    """
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000001",
        "agent_name": "claims-processing-agent",
        "tool_name": "approve_loan",
        "tool_parameters": {"loan_amount": 300000, "applicant_type": "prime"},
        "sequence_number": 2,
    })
    assert resp.json()["decision"] == "allow"


@pytest.mark.asyncio
async def test_compound_any_of_deny_first_matches(client, agent_token, admin_token):
    """Deny when first condition in any_of matches.

    Uses fetch_account_detail (not covered by any demo policy) to avoid
    interference from deny_bulk_account_lookup which now glob-matches everything
    via account_id: *.
    """
    await client.post("/policies", headers=admin_token, json={
        "name": "test_compound_or",
        "description": "Deny wildcard or null account lookups",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["fetch_account_detail"],
            "any_of": [
                {"parameter_match": {"account_id": "WILDCARD-*"}},
                {"parameter_match": {"account_id": "null"}}
            ]
        },
        "action": "deny", "severity": "high", "active": True,
    })
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000050",
        "agent_name": "support-resolution-agent",
        "tool_name": "fetch_account_detail",
        "tool_parameters": {"account_id": "WILDCARD-ALL"},
        "sequence_number": 1,
    })
    assert resp.json()["decision"] == "deny"


@pytest.mark.asyncio
async def test_compound_any_of_deny_second_matches(client, agent_token):
    """Deny when second condition in any_of matches."""
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000050",
        "agent_name": "support-resolution-agent",
        "tool_name": "fetch_account_detail",
        "tool_parameters": {"account_id": "null"},
        "sequence_number": 2,
    })
    assert resp.json()["decision"] == "deny"


@pytest.mark.asyncio
async def test_compound_any_of_allow_neither_matches(client, agent_token):
    """Allow when no conditions in any_of match."""
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000050",
        "agent_name": "support-resolution-agent",
        "tool_name": "fetch_account_detail",
        "tool_parameters": {"account_id": "ACC-12345"},
        "sequence_number": 3,
    })
    assert resp.json()["decision"] == "allow"


# ── Temporal condition tests ──────────────────────────────────────────────────
# These use ASGITransport (in-process) so the datetime mock reaches opa_client.
# Policy creation still goes through the live API (client fixture).

@asynccontextmanager
async def _asgi_client(agent_token):
    """In-process ASGI client using real agent bearer token (for datetime mocking)."""
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=agent_token,
        timeout=10.0,
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_temporal_deny_on_weekend(client, agent_token, admin_token):
    """Deny when current day is Saturday (day 5)."""
    await client.post("/policies", headers=admin_token, json={
        "name": "test_no_weekend_deploys",
        "description": "No production deploys on weekends",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["deploy_to_production"],
            "time_conditions": {"deny_days": [5, 6]}
        },
        "action": "deny", "severity": "high", "active": True,
    })
    # Saturday April 18 2026 14:00 UTC — weekday() == 5
    saturday = datetime(2026, 4, 18, 14, 0, 0, tzinfo=timezone.utc)
    with patch("app.services.opa_client.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = saturday
        mock_dt.timezone = timezone
        async with _asgi_client(agent_token) as asgi:
            resp = await asgi.post("/intercept", json={
                "session_id": _TEST_SESSION_ID,
                "agent_id": "00000000-0000-0000-0000-000000000030",
                "agent_name": "incident-response-agent",
                "tool_name": "deploy_to_production",
                "tool_parameters": {"environment": "production", "version": "v1.2.3"},
                "sequence_number": 1,
            })
    data = resp.json()
    assert data["decision"] == "deny"
    assert "time" in data["reason"]


@pytest.mark.asyncio
async def test_temporal_allow_on_weekday(client, agent_token):
    """Allow when current day is Monday (day 0)."""
    monday = datetime(2026, 4, 14, 14, 0, 0, tzinfo=timezone.utc)
    with patch("app.services.opa_client.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = monday
        mock_dt.timezone = timezone
        async with _asgi_client(agent_token) as asgi:
            resp = await asgi.post("/intercept", json={
                "session_id": _TEST_SESSION_ID,
                "agent_id": "00000000-0000-0000-0000-000000000030",
                "agent_name": "incident-response-agent",
                "tool_name": "deploy_to_production",
                "tool_parameters": {"environment": "production", "version": "v1.2.3"},
                "sequence_number": 2,
            })
    assert resp.json()["decision"] == "allow"


@pytest.mark.asyncio
async def test_temporal_deny_during_business_hours(client, agent_token, admin_token):
    """Deny restart_service during business hours 9-17 UTC."""
    await client.post("/policies", headers=admin_token, json={
        "name": "test_no_biz_hour_restarts",
        "description": "No restarts during business hours",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["restart_service"],
            "time_conditions": {"deny_hours": {"from": 9, "to": 17}}
        },
        "action": "deny", "severity": "high", "active": True,
    })
    midday = datetime(2026, 4, 14, 13, 0, 0, tzinfo=timezone.utc)
    with patch("app.services.opa_client.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = midday
        mock_dt.timezone = timezone
        async with _asgi_client(agent_token) as asgi:
            resp = await asgi.post("/intercept", json={
                "session_id": _TEST_SESSION_ID,
                "agent_id": "00000000-0000-0000-0000-000000000030",
                "agent_name": "incident-response-agent",
                "tool_name": "restart_service",
                "tool_parameters": {"service": "payment-processor"},
                "sequence_number": 1,
            })
    assert resp.json()["decision"] == "deny"


@pytest.mark.asyncio
async def test_temporal_allow_outside_business_hours(client, agent_token):
    """Allow restart_service after hours."""
    night = datetime(2026, 4, 14, 22, 0, 0, tzinfo=timezone.utc)
    with patch("app.services.opa_client.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = night
        mock_dt.timezone = timezone
        async with _asgi_client(agent_token) as asgi:
            resp = await asgi.post("/intercept", json={
                "session_id": _TEST_SESSION_ID,
                "agent_id": "00000000-0000-0000-0000-000000000030",
                "agent_name": "incident-response-agent",
                "tool_name": "restart_service",
                "tool_parameters": {"service": "payment-processor"},
                "sequence_number": 2,
            })
    assert resp.json()["decision"] == "allow"


@pytest.mark.asyncio
async def test_time_conditions_require_and_when_both_specified(client, agent_token, admin_token):
    """A policy with BOTH deny_days and deny_hours must only deny when the
    current day AND hour both match -- not when either matches alone."""
    await client.post("/policies", headers=admin_token, json={
        "name": "test_weekend_early_hours_only",
        "description": "Deny only Sat/Sun during 4-5am",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["scale_down_cluster"],
            "time_conditions": {"deny_days": [5, 6], "deny_hours": {"from": 4, "to": 5}}
        },
        "action": "deny", "severity": "high", "active": True,
    })
    # Tuesday April 14 2026 04:30 UTC -- weekday() == 1, not in [5, 6], so the
    # AND requirement must NOT be satisfied even though the hour matches.
    tuesday_early = datetime(2026, 4, 14, 4, 30, 0, tzinfo=timezone.utc)
    with patch("app.services.opa_client.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = tuesday_early
        mock_dt.timezone = timezone
        async with _asgi_client(agent_token) as asgi:
            resp = await asgi.post("/intercept", json={
                "session_id": _TEST_SESSION_ID,
                "agent_id": "00000000-0000-0000-0000-000000000030",
                "agent_name": "incident-response-agent",
                "tool_name": "scale_down_cluster",
                "tool_parameters": {"cluster": "payments"},
                "sequence_number": 1,
            })
    assert resp.json()["decision"] == "allow", (
        "day doesn't match deny_days, so the AND requirement must not fire "
        "just because the hour happens to match"
    )
    assert resp.json()["decision"] == "allow"


# ── Tool alias tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_alias_deny_on_aliased_name(client, agent_token, admin_token):
    """Policy fires on aliased tool name not in blocked_tools."""
    await client.post("/policies", headers=admin_token, json={
        "name": "test_phi_family",
        "description": "Block all PHI read variants",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["read_patient_record"],
            "tool_aliases": ["queryPatientRecord", "get_patient_data"],
            "parameter_match": {"patient_id": "PT-2024-09*"}
        },
        "action": "deny", "severity": "critical", "active": True,
    })
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000020",
        "agent_name": "clinical-documentation-agent",
        "tool_name": "queryPatientRecord",
        "tool_parameters": {"patient_id": "PT-2024-098234"},
        "sequence_number": 1,
    })
    assert resp.json()["decision"] == "deny"


@pytest.mark.asyncio
async def test_alias_deny_on_primary_name(client, agent_token):
    """Primary tool name still denied when aliases defined."""
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000020",
        "agent_name": "clinical-documentation-agent",
        "tool_name": "read_patient_record",
        "tool_parameters": {"patient_id": "PT-2024-098234"},
        "sequence_number": 2,
    })
    assert resp.json()["decision"] == "deny"


@pytest.mark.asyncio
async def test_alias_allow_unrelated_tool(client, agent_token):
    """Tool not in blocked_tools or aliases is allowed."""
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": _TEST_SESSION_ID,
        "agent_id": "00000000-0000-0000-0000-000000000020",
        "agent_name": "clinical-documentation-agent",
        "tool_name": "query_lab_results",
        "tool_parameters": {"patient_id": "PT-2024-098234"},
        "sequence_number": 3,
    })
    assert resp.json()["decision"] == "allow"


@pytest.mark.asyncio
async def test_alias_global_deny_all_http_variants(client, agent_token, admin_token):
    """Global deny policy covers all HTTP tool aliases."""
    await client.post("/policies", headers=admin_token, json={
        "name": "test_all_http_denied",
        "description": "Block all outbound HTTP tool variants",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["http_post"],
            "tool_aliases": ["http_get", "http_request", "webhook", "webhook_call"]
        },
        "action": "deny", "severity": "critical", "active": True,
    })
    for tool in ["http_post", "http_get", "http_request", "webhook", "webhook_call"]:
        resp = await client.post("/intercept", headers=agent_token, json={
            "session_id": _TEST_SESSION_ID,
            "agent_id": "00000000-0000-0000-0000-000000000030",
            "agent_name": "incident-response-agent",
            "tool_name": tool,
            "tool_parameters": {"url": "https://external.example.com"},
            "sequence_number": 1,
        })
        assert resp.json()["decision"] == "deny", f"Expected deny for tool: {tool}"
