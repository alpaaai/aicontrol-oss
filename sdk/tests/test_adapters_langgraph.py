import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock


def test_is_available_false_without_langgraph_installed(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "langgraph", None)
    from aicontrol_sdk.adapters.langgraph_adapter import LangGraphAdapter
    adapter = LangGraphAdapter()
    assert adapter.is_available() is False


def test_is_available_true_when_langgraph_installed():
    from aicontrol_sdk.adapters.langgraph_adapter import LangGraphAdapter
    adapter = LangGraphAdapter()
    assert adapter.is_available() is True


@pytest.mark.asyncio
async def test_on_tool_start_calls_intercept():
    from aicontrol_sdk.adapters.langgraph_adapter import LangGraphAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})

    adapter = LangGraphAdapter()
    adapter.patch(client)
    handler = adapter.build_callback_handler(session_id="s1")

    run_id = uuid.uuid4()
    await handler.on_tool_start(
        {"name": "query_database", "description": "..."},
        "{}",
        run_id=run_id,
        inputs={"table": "customers"},
    )

    client.intercept.assert_awaited_once()
    call_kwargs = client.intercept.call_args.kwargs
    assert call_kwargs["tool_name"] == "query_database"
    assert call_kwargs["tool_parameters"] == {"table": "customers"}
    assert call_kwargs["session_id"] == "s1"
    assert call_kwargs["sequence_number"] == 1


@pytest.mark.asyncio
async def test_on_tool_start_propagates_policy_denied():
    from aicontrol_sdk.adapters.langgraph_adapter import LangGraphAdapter
    from aicontrol_sdk.exceptions import PolicyDeniedError

    client = AsyncMock()
    client.intercept = AsyncMock(side_effect=PolicyDeniedError(reason="tool_denylisted"))

    adapter = LangGraphAdapter()
    adapter.patch(client)
    handler = adapter.build_callback_handler(session_id="s1")

    with pytest.raises(PolicyDeniedError):
        await handler.on_tool_start(
            {"name": "dangerous_tool", "description": "..."},
            "{}",
            run_id=uuid.uuid4(),
            inputs={},
        )


@pytest.mark.asyncio
async def test_on_tool_end_correlates_tool_name_via_run_id():
    """on_tool_end's real BaseCallbackHandler signature carries no tool name or
    serialized dict, only run_id/output -- unlike on_tool_start. Confirmed by
    reading the installed langchain_core.callbacks.base source this session.
    The adapter must track run_id -> tool_name from on_tool_start to report
    the correct name in report_response."""
    from aicontrol_sdk.adapters.langgraph_adapter import LangGraphAdapter

    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow"})
    client.report_response = AsyncMock(return_value={})

    adapter = LangGraphAdapter()
    adapter.patch(client)
    handler = adapter.build_callback_handler(session_id="s1")

    run_id = uuid.uuid4()
    await handler.on_tool_start(
        {"name": "query_database", "description": "..."},
        "{}",
        run_id=run_id,
        inputs={"table": "customers"},
    )
    await handler.on_tool_end("42 rows returned", run_id=run_id)

    client.report_response.assert_awaited_once()
    call_kwargs = client.report_response.call_args.kwargs
    assert call_kwargs["tool_name"] == "query_database"
    assert call_kwargs["tool_response"] == "42 rows returned"
    assert call_kwargs["session_id"] == "s1"


@pytest.mark.asyncio
async def test_on_tool_end_unknown_run_id_reports_unknown_name():
    from aicontrol_sdk.adapters.langgraph_adapter import LangGraphAdapter

    client = AsyncMock()
    client.report_response = AsyncMock(return_value={})

    adapter = LangGraphAdapter()
    adapter.patch(client)
    handler = adapter.build_callback_handler(session_id="s1")

    await handler.on_tool_end("some output", run_id=uuid.uuid4())

    call_kwargs = client.report_response.call_args.kwargs
    assert call_kwargs["tool_name"] == "unknown"


def test_extract_usage_reads_usage_metadata():
    from aicontrol_sdk.adapters.langgraph_adapter import LangGraphAdapter

    adapter = LangGraphAdapter()
    response = MagicMock()
    response.usage_metadata = {"input_tokens": 1200, "output_tokens": 340}

    assert adapter.extract_usage(response) == {"input_tokens": 1200, "output_tokens": 340}


def test_extract_usage_returns_empty_for_response_without_usage():
    from aicontrol_sdk.adapters.langgraph_adapter import LangGraphAdapter

    adapter = LangGraphAdapter()
    assert adapter.extract_usage(object()) == {}
