import pytest


@pytest.mark.asyncio
async def test_draft_endpoint_returns_pending_draft_not_active_policy(admin_token, client):
    resp = await client.post(
        "/policies/nl-draft",
        json={"description": "Block any agent from calling delete_customer_record"},
        headers=admin_token,
    )
    assert resp.status_code == 200
    assert resp.json()["requires_admin_approval"] is True
