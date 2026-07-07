import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_openai_adapter_on_tool_start_calls_intercept():
    from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = OpenAIAgentsSDKAdapter()
    assert adapter.is_available() is True
    adapter.patch(client)
    hooks = adapter.build_hooks(session_id="s1")

    fake_tool = MagicMock()
    fake_tool.name = "query_database"
    fake_context = MagicMock()
    fake_context.tool_arguments = {"table": "customers"}

    await hooks.on_tool_start(fake_context, MagicMock(), fake_tool)

    client.intercept.assert_awaited_once()
    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs["tool_name"] == "query_database"
    assert call_kwargs["session_id"] == "s1"
    assert call_kwargs["sequence_number"] == 1


@pytest.mark.asyncio
async def test_openai_adapter_propagates_policy_denied():
    from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter
    from aicontrol_sdk.exceptions import PolicyDeniedError

    client = AsyncMock()
    client.intercept = AsyncMock(side_effect=PolicyDeniedError(reason="tool_denylisted"))

    adapter = OpenAIAgentsSDKAdapter()
    adapter.patch(client)
    hooks = adapter.build_hooks(session_id="s1")

    fake_tool = MagicMock()
    fake_tool.name = "dangerous_tool"

    with pytest.raises(PolicyDeniedError):
        await hooks.on_tool_start(MagicMock(tool_arguments={}), MagicMock(), fake_tool)
