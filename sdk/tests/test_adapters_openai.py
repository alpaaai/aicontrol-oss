import pytest
from unittest.mock import AsyncMock, MagicMock


def _fake_model_response(input_tokens: int, output_tokens: int):
    from agents.items import ModelResponse
    from agents.usage import Usage

    return ModelResponse(
        output=[],
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=input_tokens + output_tokens),
        response_id="resp-1",
    )


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


@pytest.mark.asyncio
async def test_extract_usage_reads_model_response_usage():
    from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter

    adapter = OpenAIAgentsSDKAdapter()
    result = adapter.extract_usage(_fake_model_response(1200, 340))

    assert result == {"input_tokens": 1200, "output_tokens": 340}


@pytest.mark.asyncio
async def test_extract_usage_returns_empty_for_response_without_usage():
    from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter

    adapter = OpenAIAgentsSDKAdapter()
    assert adapter.extract_usage(object()) == {}


@pytest.mark.asyncio
async def test_on_llm_end_usage_attaches_to_following_tool_call():
    from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = OpenAIAgentsSDKAdapter()
    adapter.patch(client)
    hooks = adapter.build_hooks(session_id="s1")

    await hooks.on_llm_end(MagicMock(), MagicMock(), _fake_model_response(1200, 340))

    fake_tool = MagicMock()
    fake_tool.name = "query_database"
    await hooks.on_tool_start(MagicMock(tool_arguments={}), MagicMock(), fake_tool)

    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs["input_tokens"] == 1200
    assert call_kwargs["output_tokens"] == 340


@pytest.mark.asyncio
async def test_usage_does_not_attach_to_tool_call_before_the_llm_call():
    """Lag behavior: a tool call fired with no preceding on_llm_end carries no usage."""
    from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = OpenAIAgentsSDKAdapter()
    adapter.patch(client)
    hooks = adapter.build_hooks(session_id="s1")

    fake_tool = MagicMock()
    fake_tool.name = "first_tool"
    await hooks.on_tool_start(MagicMock(tool_arguments={}), MagicMock(), fake_tool)

    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs.get("input_tokens") is None
    assert call_kwargs.get("output_tokens") is None


@pytest.mark.asyncio
async def test_retried_llm_calls_accumulate_not_overwrite():
    from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = OpenAIAgentsSDKAdapter()
    adapter.patch(client)
    hooks = adapter.build_hooks(session_id="s1")

    # Simulate the SDK retrying a failed model call internally: two on_llm_end
    # firings before the next tool call.
    await hooks.on_llm_end(MagicMock(), MagicMock(), _fake_model_response(500, 100))
    await hooks.on_llm_end(MagicMock(), MagicMock(), _fake_model_response(700, 240))

    fake_tool = MagicMock()
    fake_tool.name = "query_database"
    await hooks.on_tool_start(MagicMock(tool_arguments={}), MagicMock(), fake_tool)

    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs["input_tokens"] == 1200
    assert call_kwargs["output_tokens"] == 340


@pytest.mark.asyncio
async def test_parallel_tool_call_batch_attributes_usage_to_first_call_only():
    from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = OpenAIAgentsSDKAdapter()
    adapter.patch(client)
    hooks = adapter.build_hooks(session_id="s1")

    await hooks.on_llm_end(MagicMock(), MagicMock(), _fake_model_response(1200, 340))

    tool_a = MagicMock(name="tool_a")
    tool_a.name = "tool_a"
    tool_b = MagicMock(name="tool_b")
    tool_b.name = "tool_b"

    await hooks.on_tool_start(MagicMock(tool_arguments={}), MagicMock(), tool_a)
    first_call_kwargs = client.intercept.call_args.kwargs
    await hooks.on_tool_start(MagicMock(tool_arguments={}), MagicMock(), tool_b)
    second_call_kwargs = client.intercept.call_args.kwargs

    assert first_call_kwargs["input_tokens"] == 1200
    assert first_call_kwargs["output_tokens"] == 340
    assert second_call_kwargs.get("input_tokens") is None
    assert second_call_kwargs.get("output_tokens") is None


@pytest.mark.asyncio
async def test_usage_accumulator_does_not_leak_across_concurrent_sessions():
    from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = OpenAIAgentsSDKAdapter()
    adapter.patch(client)

    hooks_s1 = adapter.build_hooks(session_id="s1")
    hooks_s2 = adapter.build_hooks(session_id="s2")

    # Only session 1's model call fires usage.
    await hooks_s1.on_llm_end(MagicMock(), MagicMock(), _fake_model_response(1200, 340))

    fake_tool = MagicMock()
    fake_tool.name = "query_database"
    await hooks_s2.on_tool_start(MagicMock(tool_arguments={}), MagicMock(), fake_tool)

    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs.get("input_tokens") is None
    assert call_kwargs.get("output_tokens") is None
