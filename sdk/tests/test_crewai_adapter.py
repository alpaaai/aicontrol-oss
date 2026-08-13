import pytest


def test_is_available_false_without_crewai_installed(monkeypatch):
    import sys
    from aicontrol_sdk.adapters.crewai_adapter import CrewAIAdapter

    monkeypatch.setitem(sys.modules, "crewai", None)
    adapter = CrewAIAdapter()
    assert adapter.is_available() is False


def test_is_available_true_with_crewai_installed():
    from aicontrol_sdk.adapters.crewai_adapter import CrewAIAdapter

    adapter = CrewAIAdapter()
    assert adapter.is_available() is True


@pytest.mark.asyncio
async def test_patch_registers_hooks_that_call_client_intercept_and_report_response():
    from unittest.mock import AsyncMock

    from crewai.hooks import ToolCallHookContext, clear_all_tool_call_hooks
    from aicontrol_sdk.adapters.crewai_adapter import CrewAIAdapter

    clear_all_tool_call_hooks()
    try:
        adapter = CrewAIAdapter()
        client = AsyncMock()
        client.intercept.return_value = {"decision": "allow"}
        adapter.patch(client)

        before_context = ToolCallHookContext(
            tool_name="delete_customer_record",
            tool_input={"customer_id": "123"},
            tool=None,
        )
        adapter.on_before_tool_call(before_context)
        client.intercept.assert_awaited_once()
        _, kwargs = client.intercept.call_args
        assert kwargs["tool_name"] == "delete_customer_record"
        assert kwargs["tool_parameters"] == {"customer_id": "123"}

        after_context = ToolCallHookContext(
            tool_name="delete_customer_record",
            tool_input={"customer_id": "123"},
            tool=None,
            raw_tool_result="deleted",
        )
        adapter.on_after_tool_call(after_context)
        client.report_response.assert_awaited_once()
    finally:
        clear_all_tool_call_hooks()


def test_patch_hook_blocks_on_policy_denied():
    from unittest.mock import AsyncMock

    from crewai.hooks import ToolCallHookContext, clear_all_tool_call_hooks
    from aicontrol_sdk.adapters.crewai_adapter import CrewAIAdapter
    from aicontrol_sdk.exceptions import PolicyDeniedError

    clear_all_tool_call_hooks()
    try:
        adapter = CrewAIAdapter()
        client = AsyncMock()
        client.intercept.side_effect = PolicyDeniedError(reason="blocked", policy_name="block_dangerous_tools")
        adapter.patch(client)

        context = ToolCallHookContext(
            tool_name="delete_customer_record",
            tool_input={"customer_id": "123"},
            tool=None,
        )
        result = adapter.on_before_tool_call(context)
        assert result is False
    finally:
        clear_all_tool_call_hooks()
