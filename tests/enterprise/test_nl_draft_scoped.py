"""NL drafting produces a scoped policy, never a rule_type.

Uses ASGITransport (in-process), not the client fixture (live server on
localhost:8001) -- same reasoning as test_policy_authoring_router.py and
tests/enterprise/test_discovery_api.py: monkeypatch and
app.dependency_overrides only affect the process they run in, and mock_llm
patches NLPolicyService in-process.
"""
import pytest
from httpx import AsyncClient, ASGITransport


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
async def test_draft_returns_scope_fields(admin_token, mock_llm):
    resp = await _post_draft(
        admin_token,
        "the claims adjuster must not release a payment over 50000 dollars on guidewire",
    )
    assert resp.status_code == 200
    draft = resp.json()["draft"]
    assert draft["principal_id"] == "claims-adjuster"
    assert draft["action_tool"] == "release_payment"
    assert draft["resource_system"] == "guidewire"
    assert draft["effect"] in ("deny", "review")
    assert draft["condition"]["numeric_conditions"]["amount"]["gt"] == 50000


@pytest.mark.asyncio
async def test_draft_never_returns_a_rule_type(admin_token, mock_llm):
    resp = await _post_draft(admin_token, "block bulk claims queries")
    assert "rule_type" not in resp.json()["draft"]


@pytest.mark.asyncio
async def test_draft_returns_a_readable_sentence(admin_token, mock_llm):
    resp = await _post_draft(
        admin_token,
        "the claims adjuster must not release a payment over 50000 dollars on guidewire",
    )
    sentence = resp.json()["sentence"]
    assert "claims-adjuster" in sentence
    for engine_word in ("forbid", "principal", "Cedar", "context."):
        assert engine_word not in sentence


@pytest.mark.asyncio
async def test_draft_is_not_persisted(admin_token, db_session, mock_llm):
    from sqlalchemy import func, select
    from app.models.schemas import Policy

    before = (await db_session.execute(select(func.count(Policy.id)))).scalar_one()
    await _post_draft(admin_token, "block bulk claims queries")
    after = (await db_session.execute(select(func.count(Policy.id)))).scalar_one()
    assert after == before


@pytest.mark.asyncio
async def test_unsupported_condition_falls_back_to_manual(admin_token, mock_llm_geofence):
    resp = await _post_draft(admin_token, "only allow calls from inside the United States")
    assert resp.json()["status"] == "requires_manual_authoring"


@pytest.mark.asyncio
async def test_draft_compiles_to_valid_cedar(admin_token, mock_llm):
    from cedarpy import PolicySet
    from app.models.schemas import Policy
    from app.services.policy_compiler import compile_policy
    import uuid

    resp = await _post_draft(
        admin_token,
        "the claims adjuster must not release a payment over 50000 dollars on guidewire",
    )
    d = resp.json()["draft"]
    policy = Policy(id=uuid.uuid4(), name="probe", **d)
    PolicySet.from_str(compile_policy(policy) + "\npermit (principal, action, resource);")
