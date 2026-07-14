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


@pytest.mark.asyncio
async def test_patch_injects_hooks_into_runner_run_when_caller_passes_none():
    """After patch(), calling agents.Runner.run() without an explicit hooks=
    kwarg must have AIControl's hooks injected automatically -- today patch()
    only stores the client and does nothing else."""
    import agents as agents_module
    from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter
    from aicontrol_sdk.intercept_client import InterceptClient
    from aicontrol_sdk.config import Config

    recorded = {}

    async def fake_run(cls, starting_agent, input, **kwargs):
        recorded["hooks"] = kwargs.get("hooks")
        return "fake-result"

    agents_module.Runner.run = classmethod(fake_run)
    # Force patch() to recapture "the original" fresh -- an earlier test in
    # this file already triggered the one-time-capture (by design, so
    # repeated real patch() calls in production never re-wrap an
    # already-patched version and stack duplicate hook injection).
    for attr in ("_aicontrol_original_run", "_aicontrol_original_run_sync", "_aicontrol_original_run_streamed"):
        if hasattr(agents_module.Runner, attr):
            delattr(agents_module.Runner, attr)

    client = InterceptClient(config=Config(url="http://x", token="t", agent_id="a"))
    adapter = OpenAIAgentsSDKAdapter()
    adapter.patch(client)

    result = await agents_module.Runner.run(starting_agent="agent", input="hi")

    assert result == "fake-result"
    assert recorded["hooks"] is not None
    from agents.lifecycle import RunHooksBase
    assert isinstance(recorded["hooks"], RunHooksBase)


@pytest.mark.asyncio
async def test_patch_does_not_override_caller_supplied_hooks():
    """If the caller passes their own hooks= explicitly, patch()'s injected
    hooks must not clobber it."""
    import agents as agents_module
    from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter
    from aicontrol_sdk.intercept_client import InterceptClient
    from aicontrol_sdk.config import Config

    recorded = {}

    async def fake_run(cls, starting_agent, input, **kwargs):
        recorded["hooks"] = kwargs.get("hooks")
        return "fake-result"

    agents_module.Runner.run = classmethod(fake_run)
    # Force patch() to recapture "the original" fresh -- an earlier test in
    # this file already triggered the one-time-capture (by design, so
    # repeated real patch() calls in production never re-wrap an
    # already-patched version and stack duplicate hook injection).
    for attr in ("_aicontrol_original_run", "_aicontrol_original_run_sync", "_aicontrol_original_run_streamed"):
        if hasattr(agents_module.Runner, attr):
            delattr(agents_module.Runner, attr)

    client = InterceptClient(config=Config(url="http://x", token="t", agent_id="a"))
    adapter = OpenAIAgentsSDKAdapter()
    adapter.patch(client)

    my_hooks = object()
    await agents_module.Runner.run(starting_agent="agent", input="hi", hooks=my_hooks)

    assert recorded["hooks"] is my_hooks
