import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_anthropic_adapter_hook_calls_intercept_and_allows():
    from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = AnthropicAgentSDKAdapter()
    assert adapter.is_available() is True
    adapter.patch(client)
    matcher = adapter.build_hook_matcher()

    hook_fn = matcher.hooks[0]
    result = await hook_fn(
        {"tool_name": "query_database", "tool_input": {"table": "customers"}, "session_id": "s1"},
        "tool-use-1",
        None,
    )

    client.intercept.assert_awaited_once()
    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs["tool_name"] == "query_database"
    assert call_kwargs["tool_parameters"] == {"table": "customers"}
    assert result == {}


@pytest.mark.asyncio
async def test_anthropic_adapter_hook_denies_on_policy_denied():
    from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter
    from aicontrol_sdk.exceptions import PolicyDeniedError

    client = AsyncMock()
    client.intercept = AsyncMock(side_effect=PolicyDeniedError(reason="tool_denylisted"))

    adapter = AnthropicAgentSDKAdapter()
    adapter.patch(client)
    matcher = adapter.build_hook_matcher()
    hook_fn = matcher.hooks[0]

    result = await hook_fn(
        {"tool_name": "dangerous_tool", "tool_input": {}, "session_id": "s1"}, "tool-use-2", None
    )

    output = result["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert output["permissionDecisionReason"] == "tool_denylisted"


@pytest.mark.asyncio
async def test_anthropic_adapter_sequence_numbers_increment_per_session():
    from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = AnthropicAgentSDKAdapter()
    adapter.patch(client)
    hook_fn = adapter.build_hook_matcher().hooks[0]

    await hook_fn({"tool_name": "t", "tool_input": {}, "session_id": "s1"}, "id1", None)
    await hook_fn({"tool_name": "t", "tool_input": {}, "session_id": "s1"}, "id2", None)

    seqs = [c.kwargs["sequence_number"] for c in client.intercept.call_args_list]
    assert seqs == [1, 2]


@pytest.mark.asyncio
async def test_patch_injects_pretooluse_hook_into_new_options():
    """After patch(), constructing a ClaudeAgentOptions() must have AIControl's
    PreToolUse HookMatcher already present in .hooks -- today patch() only
    stores the client and does nothing else."""
    from claude_agent_sdk import ClaudeAgentOptions, HookMatcher
    from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter
    from aicontrol_sdk.intercept_client import InterceptClient
    from aicontrol_sdk.config import Config

    client = InterceptClient(config=Config(url="http://x", token="t", agent_id="a"))
    adapter = AnthropicAgentSDKAdapter()
    adapter.patch(client)

    options = ClaudeAgentOptions()

    assert options.hooks is not None
    assert "PreToolUse" in options.hooks
    assert any(isinstance(m, HookMatcher) for m in options.hooks["PreToolUse"])


@pytest.mark.asyncio
async def test_patch_preserves_callers_own_pretooluse_hooks():
    """A caller-supplied PreToolUse hook set before construction must be kept
    alongside AIControl's injected one, not clobbered."""
    from claude_agent_sdk import ClaudeAgentOptions, HookMatcher
    from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter
    from aicontrol_sdk.intercept_client import InterceptClient
    from aicontrol_sdk.config import Config

    client = InterceptClient(config=Config(url="http://x", token="t", agent_id="a"))
    adapter = AnthropicAgentSDKAdapter()
    adapter.patch(client)

    my_matcher = HookMatcher(hooks=[lambda *a, **k: {}])
    options = ClaudeAgentOptions(hooks={"PreToolUse": [my_matcher]})

    assert my_matcher in options.hooks["PreToolUse"]
    assert len(options.hooks["PreToolUse"]) == 2


def _fake_assistant_message(input_tokens: int, output_tokens: int, session_id: str = "s1"):
    from claude_agent_sdk import AssistantMessage

    return AssistantMessage(
        content=[],
        model="claude-x",
        usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
        session_id=session_id,
    )


def test_extract_usage_reads_assistant_message_usage():
    from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter

    adapter = AnthropicAgentSDKAdapter()
    result = adapter.extract_usage(_fake_assistant_message(800, 210))

    assert result == {"input_tokens": 800, "output_tokens": 210}


def test_extract_usage_returns_empty_for_message_without_usage():
    from claude_agent_sdk import AssistantMessage
    from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter

    adapter = AnthropicAgentSDKAdapter()
    message = AssistantMessage(content=[], model="claude-x", usage=None, session_id="s1")

    assert adapter.extract_usage(message) == {}
    assert adapter.extract_usage(object()) == {}


async def _drain(agen):
    async for _ in agen:
        pass


async def _one_message_stream(*messages):
    for m in messages:
        yield m


@pytest.mark.asyncio
async def test_message_stream_usage_attaches_to_following_tool_call():
    from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = AnthropicAgentSDKAdapter()
    adapter.patch(client)
    hook_fn = adapter.build_hook_matcher().hooks[0]

    await _drain(adapter._wrap_message_stream(_one_message_stream(_fake_assistant_message(800, 210, "s1"))))

    await hook_fn({"tool_name": "query_database", "tool_input": {}, "session_id": "s1"}, "id1", None)

    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs["input_tokens"] == 800
    assert call_kwargs["output_tokens"] == 210


@pytest.mark.asyncio
async def test_usage_does_not_attach_to_tool_call_before_any_assistant_message():
    """Lag behavior: a tool call fired with no preceding AssistantMessage carries no usage."""
    from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = AnthropicAgentSDKAdapter()
    adapter.patch(client)
    hook_fn = adapter.build_hook_matcher().hooks[0]

    await hook_fn({"tool_name": "first_tool", "tool_input": {}, "session_id": "s1"}, "id1", None)

    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs.get("input_tokens") is None
    assert call_kwargs.get("output_tokens") is None


@pytest.mark.asyncio
async def test_retried_assistant_messages_accumulate_not_overwrite():
    from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = AnthropicAgentSDKAdapter()
    adapter.patch(client)
    hook_fn = adapter.build_hook_matcher().hooks[0]

    await _drain(adapter._wrap_message_stream(_one_message_stream(
        _fake_assistant_message(500, 100, "s1"),
        _fake_assistant_message(700, 240, "s1"),
    )))

    await hook_fn({"tool_name": "query_database", "tool_input": {}, "session_id": "s1"}, "id1", None)

    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs["input_tokens"] == 1200
    assert call_kwargs["output_tokens"] == 340


@pytest.mark.asyncio
async def test_parallel_tool_call_batch_attributes_usage_to_first_call_only():
    from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = AnthropicAgentSDKAdapter()
    adapter.patch(client)
    hook_fn = adapter.build_hook_matcher().hooks[0]

    await _drain(adapter._wrap_message_stream(_one_message_stream(_fake_assistant_message(1200, 340, "s1"))))

    await hook_fn({"tool_name": "tool_a", "tool_input": {}, "session_id": "s1"}, "id1", None)
    first_call_kwargs = client.intercept.call_args.kwargs
    await hook_fn({"tool_name": "tool_b", "tool_input": {}, "session_id": "s1"}, "id2", None)
    second_call_kwargs = client.intercept.call_args.kwargs

    assert first_call_kwargs["input_tokens"] == 1200
    assert first_call_kwargs["output_tokens"] == 340
    assert second_call_kwargs.get("input_tokens") is None
    assert second_call_kwargs.get("output_tokens") is None


@pytest.mark.asyncio
async def test_usage_does_not_leak_across_sessions():
    from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = AnthropicAgentSDKAdapter()
    adapter.patch(client)
    hook_fn = adapter.build_hook_matcher().hooks[0]

    await _drain(adapter._wrap_message_stream(_one_message_stream(_fake_assistant_message(1200, 340, "s1"))))

    await hook_fn({"tool_name": "query_database", "tool_input": {}, "session_id": "s2"}, "id1", None)

    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs.get("input_tokens") is None
    assert call_kwargs.get("output_tokens") is None


@pytest.mark.asyncio
async def test_wrap_message_stream_yields_messages_unchanged():
    from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter

    client = AsyncMock()
    adapter = AnthropicAgentSDKAdapter()
    adapter.patch(client)

    message = _fake_assistant_message(1, 1, "s1")
    seen = [m async for m in adapter._wrap_message_stream(_one_message_stream(message))]

    assert seen == [message]


@pytest.mark.asyncio
async def test_patch_wraps_client_receive_messages_and_module_query():
    """After patch(), ClaudeSDKClient.receive_messages and the module-level
    query() must both be reassigned to the adapter's wrapping generator --
    today patch() only wraps ClaudeAgentOptions.__init__."""
    import claude_agent_sdk
    from claude_agent_sdk import ClaudeSDKClient
    from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter
    from aicontrol_sdk.intercept_client import InterceptClient
    from aicontrol_sdk.config import Config

    client = InterceptClient(config=Config(url="http://x", token="t", agent_id="a"))
    adapter = AnthropicAgentSDKAdapter()
    adapter.patch(client)

    assert hasattr(ClaudeSDKClient, "_aicontrol_original_receive_messages")
    assert ClaudeSDKClient.receive_messages is not ClaudeSDKClient._aicontrol_original_receive_messages
    assert hasattr(claude_agent_sdk, "_aicontrol_original_query")
    assert claude_agent_sdk.query is not claude_agent_sdk._aicontrol_original_query
