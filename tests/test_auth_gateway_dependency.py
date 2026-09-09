import pytest
from fastapi import HTTPException

from app.core.auth import require_gateway_agent


@pytest.mark.asyncio
async def test_require_gateway_agent_rejects_admin_token():
    with pytest.raises(HTTPException) as exc_info:
        await require_gateway_agent(payload={"role": "admin", "agent_id": None})
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_gateway_agent_rejects_unscoped_agent_token():
    with pytest.raises(HTTPException) as exc_info:
        await require_gateway_agent(payload={"role": "agent", "agent_id": None})
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_gateway_agent_accepts_scoped_agent_token():
    payload = await require_gateway_agent(payload={"role": "agent", "agent_id": "abc-123"})
    assert payload["agent_id"] == "abc-123"
