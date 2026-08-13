"""Demo: LangGraph SDK adapter (Task 5 of
plans/v2/2026-08-12-consolidated-wedge-sprint-full-build-plan.md).

Wires AIControlCallbackHandler in via config={"callbacks": [...]} on a
direct tool.ainvoke() call -- LangGraph has no global monkeypatch point
the way OpenAI Agents SDK's Runner does (see langgraph_adapter.py's module
docstring), so callers pass the handler into their own invocation the same
way this demo does. Shows an allowed tool call executes normally, and a
denied one is genuinely blocked for an async-defined tool (raise_error =
True, added by the self-critique fix: LangChain's CallbackManager silently
swallows exceptions raised from on_tool_start by default, so without that
fix a "denied" tool call still executed).

Case 3 shows a real, unfixable-from-this-adapter LangChain limitation
documented in langgraph_adapter.py's module docstring: a SYNC-defined tool
(`@tool def ...`, only `_run` implemented) fires on_tool_start through
LangChain's sync CallbackManager path, whose queued-coroutine execution
swallows exceptions unconditionally -- raise_error=True has no effect
there. The identical deny decision genuinely blocks an async tool and does
NOT block a sync tool. Integrators who need this governance guarantee must
define LangGraph/LangChain tools with `async def`.

Uses a stub InterceptClient (no live AIControl API/DB required) whose
decision depends on the tool name, matching the shape of a real deny.

Scope note: this demo calls tool.ainvoke() directly rather than wrapping
it in a langgraph.prebuilt.ToolNode / full StateGraph. ToolNode was tried
first and found to swallow the callback exception even for an async tool,
before it ever reaches the point this demo verifies -- a further,
separately-scoped LangGraph-internals question this session did not chase
down. The demo shows only what is actually confirmed.

Run (from sdk/, using its own isolated venv):
  cd sdk && PYTHONPATH=<repo>/sdk/src .venv/bin/python ../scripts/demos/langgraph_demo.py
"""
import asyncio

from langchain_core.tools import tool

from aicontrol_sdk.adapters.langgraph_adapter import LangGraphAdapter
from aicontrol_sdk.exceptions import PolicyDeniedError

DENIED_TOOLS = {"delete_customer_record", "wire_transfer_sync"}


class _StubInterceptClient:
    async def intercept(self, tool_name, tool_parameters, session_id, sequence_number):
        if tool_name in DENIED_TOOLS:
            raise PolicyDeniedError(reason="tool_denylisted", policy_name="block_dangerous_tools")
        return {"decision": "allow"}

    async def report_response(self, tool_name, tool_response, session_id, sequence_number):
        return {}


@tool
async def get_account_balance(account_id: str) -> str:
    """Look up an account balance."""
    return f"Account {account_id}: $4,231.00"


@tool
async def delete_customer_record(customer_id: str) -> str:
    """Permanently delete a customer record."""
    return f"Deleted customer {customer_id}"  # never reached when denied


@tool
def wire_transfer_sync(account_id: str, amount_usd: float) -> str:
    """Wire funds out — defined as a plain sync function."""
    return f"Wired ${amount_usd} from {account_id}"  # executes despite the deny, see case 3


TOOLS_BY_NAME = {
    "get_account_balance": get_account_balance,
    "delete_customer_record": delete_customer_record,
    "wire_transfer_sync": wire_transfer_sync,
}


async def _run_case(title: str, tool_name: str, tool_args: dict) -> None:
    adapter = LangGraphAdapter()
    adapter.patch(_StubInterceptClient())
    handler = adapter.build_callback_handler(session_id="demo-session")

    print(f"\n=== {title} ===")
    try:
        result = await TOOLS_BY_NAME[tool_name].ainvoke(tool_args, config={"callbacks": [handler]})
        print(f"Tool executed. Result: {result}")
    except PolicyDeniedError as exc:
        print(f"BLOCKED before execution: {exc}")


async def main() -> None:
    await _run_case(
        "1. Allowed tool call — executes normally",
        "get_account_balance",
        {"account_id": "acct_123"},
    )
    await _run_case(
        "2. Denied async-defined tool — genuinely blocked, never executes",
        "delete_customer_record",
        {"customer_id": "cus_456"},
    )
    await _run_case(
        "3. Denied sync-defined tool — KNOWN GAP: executes anyway",
        "wire_transfer_sync",
        {"account_id": "acct_789", "amount_usd": 50000.0},
    )
    print(
        "\nCase 2 relies on AIControlCallbackHandler.raise_error = True "
        "(self-critique fix) -- without it, LangChain's CallbackManager "
        "logs the PolicyDeniedError and swallows it, and the tool would "
        "have executed anyway despite the deny decision.\n"
        "Case 3 is a genuine, unfixed-from-this-adapter LangChain "
        "limitation (see langgraph_adapter.py's module docstring): "
        "sync-defined tools dispatch on_tool_start through a code path "
        "that swallows callback exceptions unconditionally. Define "
        "LangGraph tools with `async def` if this governance guarantee "
        "matters for them."
    )


if __name__ == "__main__":
    asyncio.run(main())
