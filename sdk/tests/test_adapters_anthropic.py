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
