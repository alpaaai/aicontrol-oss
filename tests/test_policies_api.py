"""Tests for policy CRUD endpoints."""
import uuid
import pytest
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport


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
        "app.services.policy_loader.push_rego_to_opa",
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
        "rule_type": "tool_denylist",
        "condition": {"blocked_tools": ["bad_tool"]},
        "action": "deny",
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
                "condition": {}, "action": "allow",
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
        "rule_type": "tool_denylist",
        "condition": {"blocked_tools": ["bad_tool"]},
        "action": "deny",
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
        "rule_type": "tool_denylist",
        "condition": {"blocked_tools": ["bad"]},
        "action": "deny",
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
        "rule_type": "tool_denylist",
        "condition": {},
        "action": "deny",
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
        "rule_type": "tool_denylist",
        "condition": {"blocked_tools": []},
        "action": "deny",
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
        "rule_type": "parameter_match",
        "condition": {"parameter_match": {"path": {"contains_any": ["/etc/passwd"]}}},
        "action": "deny",
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
        "rule_type": "parameter_match",
        "condition": {"parameter_match": {"*": {"contains_any": ["jailbreak"]}}},
        "action": "review",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_parameter_match_rejects_flat_string_spec():
    from app.main import app
    payload = {
        "name": f"test_pm_bad_{uuid.uuid4().hex[:6]}",
        "rule_type": "parameter_match",
        "condition": {"parameter_match": {"path": "flat_string_not_allowed"}},
        "action": "deny",
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
        "rule_type": "tool_pattern",
        "condition": {"tool_name_contains": ["write", "update"]},
        "action": "review",
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
        "rule_type": "tool_pattern",
        "condition": {"tool_name_contains": []},
        "action": "review",
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
        "rule_type": "numeric_conditions",
        "condition": {"numeric_conditions": {"amount": {"op": ">", "value": 10000}}},
        "action": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_numeric_conditions_rejects_bad_op():
    from app.main import app
    payload = {
        "name": f"test_nc_bad_{uuid.uuid4().hex[:6]}",
        "rule_type": "numeric_conditions",
        "condition": {"numeric_conditions": {"amount": {"op": "neq", "value": 100}}},
        "action": "deny",
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
        "rule_type": "numeric_conditions",
        "condition": {"numeric_conditions": {"amount": {"op": ">", "value": "big"}}},
        "action": "deny",
    }
    with _auth_override("admin"), _opa_patch():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/policies", json=payload)
    assert response.status_code == 422
