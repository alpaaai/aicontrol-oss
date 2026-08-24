"""Exercises the real LLM path. Run explicitly:
    PYTHONPATH=/home/deven/aicontrol pytest -m live_llm -q
Requires a provider key in the environment. Excluded from the default run.
"""
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import settings

pytestmark = pytest.mark.live_llm


@pytest.fixture(autouse=True)
def _bypass_enterprise_license():
    from app.main import app
    from app.core.license_gate import require_enterprise_license
    app.dependency_overrides[require_enterprise_license] = lambda: None
    yield
    app.dependency_overrides.pop(require_enterprise_license, None)


async def _post_draft(admin_token, description):
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(
            "/policies/nl-draft",
            json={"description": description},
            headers=admin_token,
        )


@pytest.mark.asyncio
async def test_live_draft_produces_a_compilable_scoped_policy(admin_token, monkeypatch):
    monkeypatch.setattr(settings, "LLM_MOCK_ENABLED", False)

    resp = await _post_draft(
        admin_token,
        "the claims adjuster must not release a payment over 50000 dollars on guidewire",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "drafted", body

    draft = body["draft"]
    assert draft["action_tool"], "the live model returned no tool"
    assert draft["effect"] in ("deny", "review")

    from cedarpy import PolicySet
    from app.models.schemas import Policy
    from app.services.policy_compiler import compile_policy

    policy = Policy(id=uuid.uuid4(), name="live-probe", **draft)
    PolicySet.from_str(compile_policy(policy) + "\npermit (principal, action, resource);")


@pytest.mark.asyncio
async def test_live_path_rejects_an_unsupported_condition_cleanly(admin_token, monkeypatch):
    monkeypatch.setattr(settings, "LLM_MOCK_ENABLED", False)
    resp = await _post_draft(admin_token, "only allow tool calls from inside the United States")
    assert resp.status_code == 200
    assert resp.json()["status"] == "requires_manual_authoring"
