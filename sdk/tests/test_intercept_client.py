import uuid
import httpx
import pytest


def _client_with_transport(config, handler):
    from aicontrol_sdk.intercept_client import InterceptClient
    transport = httpx.MockTransport(handler)
    return InterceptClient(config=config, transport=transport)


@pytest.mark.asyncio
async def test_intercept_sends_correct_payload(config):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = httpx.Request.read(request) and request
        import json as _json
        captured["body"] = _json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"decision": "allow", "reason": "default_allow", "audit_event_id": str(uuid.uuid4())})

    client = _client_with_transport(config, handler)
    session_id = str(uuid.uuid4())
    result = await client.intercept(
        tool_name="query_database",
        tool_parameters={"table": "customers"},
        session_id=session_id,
        sequence_number=1,
    )

    assert captured["auth"] == "Bearer tok-123"
    assert captured["body"]["tool_name"] == "query_database"
    assert captured["body"]["agent_id"] == "agent-1"
    assert captured["body"]["session_id"] == session_id
    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_intercept_includes_token_fields_only_when_provided(config):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json
        captured["body"] = _json.loads(request.content)
        return httpx.Response(200, json={"decision": "allow", "reason": "default_allow", "audit_event_id": str(uuid.uuid4())})

    client = _client_with_transport(config, handler)
    await client.intercept(
        tool_name="t", tool_parameters={}, session_id=str(uuid.uuid4()), sequence_number=1,
        input_tokens=100, output_tokens=20, cost_usd=0.002,
    )

    assert captured["body"]["input_tokens"] == 100
    assert captured["body"]["output_tokens"] == 20
    assert captured["body"]["cost_usd"] == 0.002


@pytest.mark.asyncio
async def test_intercept_raises_policy_denied_on_deny(config):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "decision": "deny", "reason": "tool_denylisted",
            "audit_event_id": str(uuid.uuid4()), "policy_name": "block_dangerous_tools",
        })

    from aicontrol_sdk.exceptions import PolicyDeniedError
    client = _client_with_transport(config, handler)
    with pytest.raises(PolicyDeniedError) as exc_info:
        await client.intercept(tool_name="t", tool_parameters={}, session_id=str(uuid.uuid4()), sequence_number=1)
    assert exc_info.value.reason == "tool_denylisted"
    assert exc_info.value.policy_name == "block_dangerous_tools"


@pytest.mark.asyncio
async def test_intercept_raises_review_pending_on_review(config):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "decision": "review", "reason": "requires_review",
            "audit_event_id": str(uuid.uuid4()), "review_id": "rev-1",
        })

    from aicontrol_sdk.exceptions import ReviewPendingError
    client = _client_with_transport(config, handler)
    with pytest.raises(ReviewPendingError) as exc_info:
        await client.intercept(tool_name="t", tool_parameters={}, session_id=str(uuid.uuid4()), sequence_number=1)
    assert exc_info.value.review_id == "rev-1"


@pytest.mark.asyncio
async def test_intercept_fail_closed_raises_unavailable_on_connection_error(config):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    from aicontrol_sdk.exceptions import AIControlUnavailableError
    client = _client_with_transport(config, handler)
    with pytest.raises(AIControlUnavailableError):
        await client.intercept(tool_name="t", tool_parameters={}, session_id=str(uuid.uuid4()), sequence_number=1)


@pytest.mark.asyncio
async def test_intercept_fail_open_returns_synthetic_allow_on_connection_error(config_fail_open):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _client_with_transport(config_fail_open, handler)
    result = await client.intercept(tool_name="t", tool_parameters={}, session_id=str(uuid.uuid4()), sequence_number=1)
    assert result["decision"] == "allow"
    assert result["reason"] == "aicontrol_unavailable_fail_open"
