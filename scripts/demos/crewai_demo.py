"""Demo: CrewAI SDK adapter (Task 5b of
plans/v2/2026-08-12-consolidated-wedge-sprint-full-build-plan.md).

Registers the adapter's real process-global hooks via patch(), then drives
tool execution through crewai.hooks.run_before_tool_call_hooks -- the same
dispatch function crewai.utilities.tool_utils.execute_tool_and_check_finality
calls internally before invoking a tool -- rather than calling the
adapter's own on_before_tool_call method directly, so this demonstrates
the real engine-level blocking contract, not just our own hook function in
isolation.

Uses a stub InterceptClient (no live AIControl API/DB required) whose
decision depends on the tool name, matching the shape of a real deny.

Run (from sdk/, using its own isolated venv — crewai requires Python >=3.12,
see docs/state's note on the sdk/.venv rebuild):
  cd sdk && PYTHONPATH=<repo>/sdk/src .venv/bin/python ../scripts/demos/crewai_demo.py
"""
from crewai.hooks import ToolCallHookContext, clear_all_tool_call_hooks
from crewai.hooks.tool_hooks import run_before_tool_call_hooks

from aicontrol_sdk.adapters.crewai_adapter import CrewAIAdapter
from aicontrol_sdk.exceptions import PolicyDeniedError

DENIED_TOOLS = {"delete_customer_record"}


class _StubInterceptClient:
    async def intercept(self, tool_name, tool_parameters, session_id, sequence_number):
        if tool_name in DENIED_TOOLS:
            raise PolicyDeniedError(reason="tool_denylisted", policy_name="block_dangerous_tools")
        return {"decision": "allow"}

    async def report_response(self, tool_name, tool_response, session_id, sequence_number):
        return {}


def _execute_if_not_blocked(tool_name: str, tool_input: dict) -> None:
    print(f"\n=== {tool_name} ===")
    context = ToolCallHookContext(tool_name=tool_name, tool_input=tool_input, tool=None)
    blocked = run_before_tool_call_hooks(context)
    if blocked:
        print("BLOCKED before execution — HookAborted, tool never ran")
        return
    print(f"Tool executed with input: {context.tool_input}")


def main() -> None:
    clear_all_tool_call_hooks()
    try:
        adapter = CrewAIAdapter()
        adapter.patch(_StubInterceptClient())

        _execute_if_not_blocked("get_account_balance", {"account_id": "acct_123"})
        _execute_if_not_blocked("delete_customer_record", {"customer_id": "cus_456"})

        print(
            "\nBoth cases went through crewai.hooks.run_before_tool_call_hooks -- "
            "the real function CrewAI's own tool-execution machinery calls before "
            "running a tool, not a direct call to the adapter's own method."
        )
    finally:
        clear_all_tool_call_hooks()


if __name__ == "__main__":
    main()
