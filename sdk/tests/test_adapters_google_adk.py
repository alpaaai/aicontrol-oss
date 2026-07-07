import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_google_adk_adapter_before_tool_callback_allows_returns_none():
    from aicontrol_sdk.adapters.google_adk import GoogleADKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = GoogleADKAdapter()
    assert adapter.is_available() is True
    adapter.patch(client)
    plugin = adapter.build_plugin()

    fake_tool = MagicMock()
    fake_tool.name = "query_database"
    fake_context = MagicMock()
    fake_context.session_id = "s1"

    result = await plugin.before_tool_callback(
        tool=fake_tool, tool_args={"table": "customers"}, tool_context=fake_context
    )

    assert result is None
    client.intercept.assert_awaited_once()
    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs["tool_name"] == "query_database"
    assert call_kwargs["tool_parameters"] == {"table": "customers"}


@pytest.mark.asyncio
async def test_google_adk_adapter_before_tool_callback_short_circuits_on_deny():
    from aicontrol_sdk.adapters.google_adk import GoogleADKAdapter
    from aicontrol_sdk.exceptions import PolicyDeniedError

    client = AsyncMock()
    client.intercept = AsyncMock(side_effect=PolicyDeniedError(reason="tool_denylisted"))

    adapter = GoogleADKAdapter()
    adapter.patch(client)
    plugin = adapter.build_plugin()

    fake_tool = MagicMock()
    fake_tool.name = "dangerous_tool"
    fake_context = MagicMock()
    fake_context.session_id = "s1"

    result = await plugin.before_tool_callback(tool=fake_tool, tool_args={}, tool_context=fake_context)

    assert result is not None
    assert "tool_denylisted" in result["error"]
