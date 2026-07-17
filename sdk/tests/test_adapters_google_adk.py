import pytest
from unittest.mock import AsyncMock, MagicMock

# Captured once, at import time, before any test calls patch() -- the tests
# below reset Runner.__init__ back to this pristine reference before each
# patch() call, so one test's monkeypatching never leaks into the next.
from google.adk.runners import Runner as _Runner
_PRISTINE_RUNNER_INIT = _Runner.__init__


def _reset_runner_patch_state():
    _Runner.__init__ = _PRISTINE_RUNNER_INIT
    if hasattr(_Runner, "_aicontrol_original_init"):
        delattr(_Runner, "_aicontrol_original_init")


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


@pytest.mark.asyncio
async def test_patch_injects_plugin_into_new_runner():
    """After patch(), constructing a Runner() must have AIControl's plugin
    already present in its plugins list -- today patch() only stores the
    client and does nothing else."""
    from google.adk.runners import Runner
    from aicontrol_sdk.adapters.google_adk import GoogleADKAdapter
    from aicontrol_sdk.intercept_client import InterceptClient
    from aicontrol_sdk.config import Config

    _reset_runner_patch_state()

    client = InterceptClient(config=Config(url="http://x", token="t", agent_id="a"))
    adapter = GoogleADKAdapter()
    adapter.patch(client)

    runner = Runner(app_name="test-app", agent=MagicMock(), session_service=MagicMock())

    assert any(getattr(p, "name", None) == "aicontrol" for p in runner.plugin_manager.plugins)


@pytest.mark.asyncio
async def test_patch_preserves_callers_own_plugins():
    """A caller-supplied plugins list must be kept alongside AIControl's
    injected plugin, not replaced."""
    from google.adk.runners import Runner
    from google.adk.plugins.base_plugin import BasePlugin
    from aicontrol_sdk.adapters.google_adk import GoogleADKAdapter
    from aicontrol_sdk.intercept_client import InterceptClient
    from aicontrol_sdk.config import Config

    class MyPlugin(BasePlugin):
        def __init__(self):
            super().__init__(name="my-plugin")

    _reset_runner_patch_state()

    client = InterceptClient(config=Config(url="http://x", token="t", agent_id="a"))
    adapter = GoogleADKAdapter()
    adapter.patch(client)

    my_plugin = MyPlugin()
    runner = Runner(
        app_name="test-app", agent=MagicMock(), session_service=MagicMock(),
        plugins=[my_plugin],
    )

    names = [getattr(p, "name", None) for p in runner.plugin_manager.plugins]
    assert "my-plugin" in names
    assert "aicontrol" in names


def _fake_llm_response(prompt_tokens: int, candidates_tokens: int):
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types

    usage_metadata = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=prompt_tokens,
        candidates_token_count=candidates_tokens,
        total_token_count=prompt_tokens + candidates_tokens,
    )
    return LlmResponse(usage_metadata=usage_metadata)


@pytest.mark.asyncio
async def test_extract_usage_reads_llm_response_usage_metadata():
    from aicontrol_sdk.adapters.google_adk import GoogleADKAdapter

    adapter = GoogleADKAdapter()
    result = adapter.extract_usage(_fake_llm_response(800, 210))

    assert result == {"input_tokens": 800, "output_tokens": 210}


@pytest.mark.asyncio
async def test_extract_usage_returns_empty_for_response_without_usage_metadata():
    from aicontrol_sdk.adapters.google_adk import GoogleADKAdapter

    adapter = GoogleADKAdapter()
    assert adapter.extract_usage(object()) == {}


@pytest.mark.asyncio
async def test_after_model_callback_usage_attaches_to_following_tool_call():
    from aicontrol_sdk.adapters.google_adk import GoogleADKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = GoogleADKAdapter()
    adapter.patch(client)
    plugin = adapter.build_plugin()

    fake_context = MagicMock()
    fake_context.session_id = "s1"

    await plugin.after_model_callback(callback_context=fake_context, llm_response=_fake_llm_response(800, 210))

    fake_tool = MagicMock()
    fake_tool.name = "query_database"
    await plugin.before_tool_callback(tool=fake_tool, tool_args={}, tool_context=fake_context)

    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs["input_tokens"] == 800
    assert call_kwargs["output_tokens"] == 210


@pytest.mark.asyncio
async def test_google_adk_retried_llm_calls_accumulate_not_overwrite():
    from aicontrol_sdk.adapters.google_adk import GoogleADKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = GoogleADKAdapter()
    adapter.patch(client)
    plugin = adapter.build_plugin()

    fake_context = MagicMock()
    fake_context.session_id = "s1"

    await plugin.after_model_callback(callback_context=fake_context, llm_response=_fake_llm_response(300, 50))
    await plugin.after_model_callback(callback_context=fake_context, llm_response=_fake_llm_response(500, 160))

    fake_tool = MagicMock()
    fake_tool.name = "query_database"
    await plugin.before_tool_callback(tool=fake_tool, tool_args={}, tool_context=fake_context)

    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs["input_tokens"] == 800
    assert call_kwargs["output_tokens"] == 210


@pytest.mark.asyncio
async def test_google_adk_parallel_tool_call_batch_attributes_usage_to_first_call_only():
    from aicontrol_sdk.adapters.google_adk import GoogleADKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = GoogleADKAdapter()
    adapter.patch(client)
    plugin = adapter.build_plugin()

    fake_context = MagicMock()
    fake_context.session_id = "s1"

    await plugin.after_model_callback(callback_context=fake_context, llm_response=_fake_llm_response(800, 210))

    tool_a = MagicMock()
    tool_a.name = "tool_a"
    tool_b = MagicMock()
    tool_b.name = "tool_b"

    await plugin.before_tool_callback(tool=tool_a, tool_args={}, tool_context=fake_context)
    first_call_kwargs = client.intercept.call_args.kwargs
    await plugin.before_tool_callback(tool=tool_b, tool_args={}, tool_context=fake_context)
    second_call_kwargs = client.intercept.call_args.kwargs

    assert first_call_kwargs["input_tokens"] == 800
    assert first_call_kwargs["output_tokens"] == 210
    assert second_call_kwargs.get("input_tokens") is None
    assert second_call_kwargs.get("output_tokens") is None


@pytest.mark.asyncio
async def test_google_adk_usage_does_not_leak_across_sessions():
    from aicontrol_sdk.adapters.google_adk import GoogleADKAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = GoogleADKAdapter()
    adapter.patch(client)
    plugin = adapter.build_plugin()

    ctx_s1 = MagicMock()
    ctx_s1.session_id = "s1"
    ctx_s2 = MagicMock()
    ctx_s2.session_id = "s2"

    await plugin.after_model_callback(callback_context=ctx_s1, llm_response=_fake_llm_response(800, 210))

    fake_tool = MagicMock()
    fake_tool.name = "query_database"
    await plugin.before_tool_callback(tool=fake_tool, tool_args={}, tool_context=ctx_s2)

    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs.get("input_tokens") is None
    assert call_kwargs.get("output_tokens") is None
