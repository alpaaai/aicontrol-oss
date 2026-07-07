import json
import httpx
import pytest


def _client_with_transport(config, handler):
    from aicontrol_sdk.registration_client import RegistrationClient
    transport = httpx.MockTransport(handler)
    return RegistrationClient(config=config, transport=transport)


@pytest.mark.asyncio
async def test_register_agent_sends_name_and_returns_id(config):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        captured["path"] = request.url.path
        return httpx.Response(201, json={
            "id": "agent-999", "name": "my-agent", "owner": "sdk-auto-registered",
            "status": "active", "framework": None, "approved_tools": [], "approved_by": None,
        })

    client = _client_with_transport(config, handler)
    agent_id = await client.register_agent(name="my-agent")

    assert captured["path"] == "/agents/register"
    assert captured["auth"] == "Bearer tok-123"
    assert captured["body"]["name"] == "my-agent"
    assert agent_id == "agent-999"


@pytest.mark.asyncio
async def test_register_agent_caches_result_across_calls(config):
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(201, json={
            "id": "agent-999", "name": "my-agent", "owner": "sdk-auto-registered",
            "status": "active", "framework": None, "approved_tools": [], "approved_by": None,
        })

    client = _client_with_transport(config, handler)
    first = await client.register_agent(name="my-agent")
    second = await client.register_agent(name="my-agent")

    assert first == second == "agent-999"
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_register_agent_passes_framework(config):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={
            "id": "agent-999", "name": "my-agent", "owner": "sdk-auto-registered",
            "status": "active", "framework": "anthropic", "approved_tools": [], "approved_by": None,
        })

    client = _client_with_transport(config, handler)
    await client.register_agent(name="my-agent", framework="anthropic")

    assert captured["body"]["framework"] == "anthropic"
