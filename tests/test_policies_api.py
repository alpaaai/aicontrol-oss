"""Tests for policy CRUD endpoints."""
import uuid
import pytest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.routers.policies import validate_rate_limit_condition, validate_scope


@contextmanager
def _auth_override(role: str = "admin"):
    from app.main import app
    from app.core.auth import _get_verified_token
    app.dependency_overrides[_get_verified_token] = lambda: {"role": role}
    try:
        yield
    finally:
        app.dependency_overrides.pop(_get_verified_token, None)


def _opa_patch():
    return patch(
        "app.routers.policies.invalidate_policy_set_cache",
        new=AsyncMock(return_value=None)
    )


@pytest.mark.asyncio
async def test_list_policies_returns_200():
    from app.main import app
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/policies")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_policies_returns_list():
    from app.main import app
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/policies")
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_policy_returns_201():
    from app.main import app
    payload = {
        "name": f"test_policy_{uuid.uuid4().hex[:6]}",
        "condition": {"blocked_tools": ["bad_tool"]},
        "effect": "deny",
        "severity": "high",
        "description": "Test policy",
        "compliance_frameworks": [],
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_policy_requires_admin():
    from app.main import app
    with _auth_override("agent"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json={
                "name": "test", "rule_type": "default_allow",
                "condition": {}, "effect": "allow",
                "severity": "low", "compliance_frameworks": [],
            })
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_policy_returns_404_for_missing():
    from app.main import app
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.delete(f"/policies/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_policies_with_human_admin_jwt_returns_200():
    """Human admin JWT must pass require_admin on the policies route."""
    from datetime import datetime, timedelta
    from jose import jwt as jose_jwt
    from app.core.config import settings
    from app.main import app

    payload = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "email": "test_human@aicontrol.dev",
        "role": "admin",
        "type": "human",
        "exp": datetime.utcnow() + timedelta(hours=8),
    }
    token = jose_jwt.encode(payload, settings.secret_key, algorithm="HS256")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/policies", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_policy_model_has_library_priority_category():
    from app.models.schemas import Policy
    assert hasattr(Policy, "library")
    assert hasattr(Policy, "priority")
    assert hasattr(Policy, "category")


@pytest.mark.asyncio
async def test_create_policy_response_includes_new_fields():
    from app.main import app
    payload = {
        "name": f"test_newfields_{uuid.uuid4().hex[:6]}",
        "condition": {"blocked_tools": ["bad_tool"]},
        "effect": "deny",
        "priority": 50,
        "library": False,
        "category": "Dangerous Operations",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["priority"] == 50
    assert body["library"] is False
    assert body["category"] == "Dangerous Operations"


@pytest.mark.asyncio
async def test_list_library_policies_returns_200():
    from app.main import app
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/policies/library")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_list_library_policies_excludes_non_library():
    from app.main import app
    non_lib_name = f"not_lib_{uuid.uuid4().hex[:6]}"
    payload = {
        "name": non_lib_name,
        "condition": {"blocked_tools": ["bad"]},
        "effect": "deny",
        "library": False,
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/policies", json=payload)
            response = await client.get("/policies/library")
    body = response.json()
    names = [p["name"] for p in body]
    assert non_lib_name not in names


@pytest.mark.asyncio
async def test_list_library_policies_requires_admin():
    from app.main import app
    with _auth_override("agent"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/policies/library")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_tool_denylist_requires_blocked_tools():
    from app.main import app
    payload = {
        "name": f"test_val_td_{uuid.uuid4().hex[:6]}",
        "condition": {},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_tool_denylist_rejects_empty_blocked_tools():
    from app.main import app
    payload = {
        "name": f"test_val_td2_{uuid.uuid4().hex[:6]}",
        "condition": {"blocked_tools": []},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 422


def test_validate_rate_limit_condition_does_not_require_tools_key():
    """A rate_limit condition scoped entirely by the policy's action_tool (Cedar
    scope), with no condition.tools list at all, must not be rejected here --
    that binding requirement belongs to validate_scope, which is action_tool-aware."""
    condition = {"rate_limit": {"max_calls": 20, "window": "session"}}
    errors = validate_rate_limit_condition(condition)
    assert errors == []


def test_validate_rate_limit_condition_still_validates_max_calls_and_window():
    condition = {"rate_limit": {"max_calls": 0, "window": "not-a-window"}}
    errors = validate_rate_limit_condition(condition)
    assert errors


def test_validate_scope_accepts_rate_limit_bound_via_action_tool():
    """rate_limit's tool binding may come from action_tool scope instead of a
    condition.tools list -- e.g. example_rate_limit_sensitive_reads, which
    scopes via action_tool='read_record' with no 'tools' key at all."""
    body = SimpleNamespace(principal_id=None, action_tool="read_record", resource_system=None)
    condition = {"rate_limit": {"max_calls": 20, "window": "session"}}
    errors = validate_scope(body, condition)
    assert errors == []


def test_validate_scope_accepts_rate_limit_bound_via_tool_name_in():
    """rate_limit_external_api_calls binds its tool list via tool_name_in, not
    the 'tools'/'blocked_tools' spellings validate_scope's bound check used to
    recognize exclusively."""
    body = SimpleNamespace(principal_id=None, action_tool=None, resource_system=None)
    condition = {
        "rate_limit": {"max_calls": 20, "window": "60m"},
        "tool_name_in": ["http_request", "post_webhook"],
    }
    errors = validate_scope(body, condition)
    assert errors == []


def test_validate_scope_rejects_condition_that_compiles_to_no_when_clause():
    """Defense in depth: even if validate_condition somehow let a degenerate
    condition through, validate_scope must still catch it by checking what the
    condition actually compiles to -- not just whether the dict is non-empty."""
    body = SimpleNamespace(principal_id=None, action_tool=None, resource_system=None)
    errors = validate_scope(body, {"tool_name_in": []})
    assert errors


def test_validate_scope_accepts_condition_that_compiles_to_a_when_clause():
    body = SimpleNamespace(principal_id=None, action_tool=None, resource_system=None)
    errors = validate_scope(body, {"tool_name_in": ["bash"]})
    assert errors == []


@pytest.mark.asyncio
async def test_create_tool_name_in_valid():
    from app.main import app
    payload = {
        "name": f"test_tni_{uuid.uuid4().hex[:6]}",
        "condition": {"tool_name_in": ["bash", "exec_command"]},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_create_tool_name_in_rejects_empty_list():
    """An empty tool_name_in list compiles to no Cedar `when` clause at all --
    the policy would forbid every call from every agent. See validate_scope's
    compiled-emptiness check."""
    from app.main import app
    payload = {
        "name": f"test_tni_bad_{uuid.uuid4().hex[:6]}",
        "condition": {"tool_name_in": []},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_tool_aliases_rejects_empty_list():
    from app.main import app
    payload = {
        "name": f"test_talias_bad_{uuid.uuid4().hex[:6]}",
        "condition": {"tool_aliases": []},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_tools_rejects_empty_list():
    from app.main import app
    payload = {
        "name": f"test_tools_bad_{uuid.uuid4().hex[:6]}",
        "condition": {"tools": []},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_parameter_match_valid():
    from app.main import app
    payload = {
        "name": f"test_pm_{uuid.uuid4().hex[:6]}",
        "condition": {"parameter_match": {"path": {"contains_any": ["/etc/passwd"]}}},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_parameter_match_wildcard_valid():
    from app.main import app
    payload = {
        "name": f"test_pm_wc_{uuid.uuid4().hex[:6]}",
        "condition": {"parameter_match": {"*": {"contains_any": ["jailbreak"]}}},
        "effect": "review",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_parameter_match_accepts_a_scalar_spec():
    """A flat scalar is base.rego's own parameter_match spelling -- exact
    equality, or a glob when it contains * or ?. It used to be rejected because
    the standalone parameter_match rule_type demanded the object form while
    tool_denylist policies accepted scalars; with rule_type gone, one rule has to
    hold for both, and every demo seed uses the scalar form."""
    from app.main import app
    payload = {
        "name": f"test_pm_scalar_{uuid.uuid4().hex[:6]}",
        "condition": {"parameter_match": {"path": "/etc/passwd"}},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_create_parameter_match_rejects_a_list_spec():
    """Still rejected: a value that is neither a scalar nor a
    contains_any/equals object has no meaning to the compiler."""
    from app.main import app
    payload = {
        "name": f"test_pm_bad_{uuid.uuid4().hex[:6]}",
        "condition": {"parameter_match": {"path": ["not", "valid"]}},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_tool_pattern_valid():
    from app.main import app
    payload = {
        "name": f"test_tp_{uuid.uuid4().hex[:6]}",
        "condition": {"tool_name_contains": ["write", "update"]},
        "effect": "review",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_tool_pattern_rejects_empty_patterns():
    from app.main import app
    payload = {
        "name": f"test_tp_bad_{uuid.uuid4().hex[:6]}",
        "condition": {"tool_name_contains": []},
        "effect": "review",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_numeric_conditions_valid():
    from app.main import app
    payload = {
        "name": f"test_nc_{uuid.uuid4().hex[:6]}",
        "condition": {"numeric_conditions": {"amount": {"op": ">", "value": 10000}}},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_numeric_conditions_compact_form_valid():
    """The compact {"amount": {"gt": 50000}} spelling (op as the key) is what
    policy_compiler._numeric_conditions and the demo seeds actually use --
    review_high_value_claim_payment among them. Not just the long
    {"op": ..., "value": ...} form."""
    from app.main import app
    payload = {
        "name": f"test_nc_compact_{uuid.uuid4().hex[:6]}",
        "condition": {"numeric_conditions": {"amount": {"gt": 50000}}},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_create_numeric_conditions_compact_form_rejects_bad_op():
    from app.main import app
    payload = {
        "name": f"test_nc_compact_bad_{uuid.uuid4().hex[:6]}",
        "condition": {"numeric_conditions": {"amount": {"neq": 100}}},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_numeric_conditions_rejects_bad_op():
    from app.main import app
    payload = {
        "name": f"test_nc_bad_{uuid.uuid4().hex[:6]}",
        "condition": {"numeric_conditions": {"amount": {"op": "neq", "value": 100}}},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_numeric_conditions_rejects_non_number_value():
    from app.main import app
    payload = {
        "name": f"test_nc_bad2_{uuid.uuid4().hex[:6]}",
        "condition": {"numeric_conditions": {"amount": {"op": ">", "value": "big"}}},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_activate_baseline_standard_returns_200():
    from app.main import app
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/policies/activate-baseline", json={"mode": "standard"}
            )
    assert response.status_code == 200
    body = response.json()
    assert "activated" in body
    assert isinstance(body["activated"], list)


@pytest.mark.asyncio
async def test_activate_baseline_strict_returns_more_than_standard():
    from app.main import app
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            strict_response = await client.post(
                "/policies/activate-baseline", json={"mode": "strict"}
            )
    body = strict_response.json()
    assert len(body["activated"]) >= 4


@pytest.mark.asyncio
async def test_activate_baseline_rejects_invalid_mode():
    from app.main import app
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/policies/activate-baseline", json={"mode": "extreme"}
            )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_activate_baseline_requires_admin():
    from app.main import app
    with _auth_override("agent"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/policies/activate-baseline", json={"mode": "standard"}
            )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_policy_rejects_unsupported_numeric_operator():
    """A tool_denylist policy with numeric_conditions operator 'neq' (not
    implemented by base.rego's numeric_op_passes) must be rejected at
    creation, not silently accepted as a policy that will never fire."""
    from app.main import app
    payload = {
        "name": f"test_reject_neq_{uuid.uuid4().hex[:6]}",
        "condition": {
            "blocked_tools": ["some_tool"],
            "numeric_conditions": [
                {"parameter": "amount", "operator": "neq", "value": 100}
            ],
        },
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 422
    assert "operator" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_policy_rejects_malformed_time_conditions():
    """A tool_denylist policy with deny_hours using 'start'/'end' instead of
    the real 'from'/'to' keys base.rego expects must be rejected at
    creation."""
    from app.main import app
    payload = {
        "name": f"test_reject_badtime_{uuid.uuid4().hex[:6]}",
        "condition": {
            "blocked_tools": ["some_tool"],
            "time_conditions": {"deny_hours": {"start": 9, "end": 17}},
        },
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 422
    assert "time_conditions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_policy_accepts_valid_numeric_and_time_conditions():
    """Sanity check: correctly-shaped numeric_conditions/time_conditions
    must still be accepted."""
    from app.main import app
    payload = {
        "name": f"test_accept_valid_nt_{uuid.uuid4().hex[:6]}",
        "condition": {
            "blocked_tools": ["some_other_tool"],
            "numeric_conditions": [
                {"parameter": "amount", "operator": "gt", "value": 100}
            ],
            "time_conditions": {"deny_days": [5, 6], "deny_hours": {"from": 9, "to": 17}},
        },
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_policy_rejects_blank_name():
    """POST /policies with an empty name must be rejected, not silently accepted."""
    from app.main import app
    payload = {
        "name": "",
        "condition": {"blocked_tools": ["some_tool"]},
        "effect": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 422
