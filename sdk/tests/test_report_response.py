"""Tests for InterceptClient.report_response (WS-E). Mirrors the exact
MockTransport pattern already used in tests/test_intercept_client.py --
InterceptClient is constructed with a Config + httpx transport, not a
base_url/api_key pair."""
import json
import uuid

import httpx
import pytest


def _client_with_transport(config, handler):
    from aicontrol_sdk.intercept_client import InterceptClient
    transport = httpx.MockTransport(handler)
    return InterceptClient(config=config, transport=transport)


@pytest.mark.asyncio
async def test_report_response_posts_to_the_new_endpoint(config):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={
            "decision": "allow", "reason": "response_scan_clean", "audit_event_id": str(uuid.uuid4()),
        })

    client = _client_with_transport(config, handler)
    session_id = str(uuid.uuid4())
    result = await client.report_response(
        tool_name="test_tool", tool_response={"ok": True}, session_id=session_id, sequence_number=1,
    )

    assert captured["path"] == "/intercept/report-response"
    assert captured["auth"] == "Bearer tok-123"
    assert captured["body"]["tool_name"] == "test_tool"
    assert captured["body"]["agent_id"] == "agent-1"
    assert captured["body"]["session_id"] == session_id
    assert captured["body"]["tool_response"] == {"ok": True}
    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_report_response_never_raises_on_connection_failure(config):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _client_with_transport(config, handler)
    result = await client.report_response(
        tool_name="test_tool", tool_response={"ok": True}, session_id=str(uuid.uuid4()), sequence_number=1,
    )
    assert result == {"decision": "allow", "reason": "report_response_unavailable"}
