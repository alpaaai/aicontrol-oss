"""Adapter for CrewAI (crewai).

Step 1 finding (not scoped by any prior research pass): CrewAI's
step_callback/task_callback fire per ReAct-loop iteration, after the tool
has already executed -- no pre-execution granularity, and a "step" is not
always a tool call (a final-answer step has none). crewai_event_bus's
ToolUsageStartedEvent looked more promising (fires before execution) but
CrewAIEventsBus.emit() is fire-and-forget (sync handlers run in a thread
pool, async handlers in a background loop) -- the caller in
tools/tool_usage.py never awaits/joins the returned Future, so a listener
cannot reliably block before the tool runs.

The actual per-tool-call, blocking hook is crewai.hooks'
register_before_tool_call_hook/register_after_tool_call_hook (backing
utilities/tool_utils.py's execute_tool_and_check_finality, which calls
run_before_tool_call_hooks synchronously before invoking the tool and
raises HookAborted -- caught, execution blocked -- when a hook returns
False). This gives the same call-then-maybe-block granularity as the
other three adapters, unlike step_callback or the event bus.

These hooks are process-global (crewai has no per-run injection point
comparable to OpenAI Agents SDK's Runner.run(hooks=...)), so patch()
registers one pair of hooks for the process and assigns tool calls to a
single per-process session, the same convention aicontrol_sdk.decorator
already uses for its module-level default session.

Hooks are synchronous callables; InterceptClient.intercept/report_response
are async. _run_sync bridges the two -- asyncio.run() when no loop is
running (CrewAI's default sync kickoff path), a worker thread running its
own loop when one is (crew.kickoff_async()), since asyncio.run() raises
if called from inside a running loop.
"""
import asyncio
import itertools
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from aicontrol_sdk.exceptions import PolicyDeniedError, ReviewPendingError
from aicontrol_sdk.intercept_client import InterceptClient


def _run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class CrewAIAdapter:
    name = "crewai"

    def is_available(self) -> bool:
        try:
            import crewai  # noqa: F401
            return True
        except ImportError:
            return False

    def patch(self, client: InterceptClient) -> None:
        """Registers process-global before/after tool-call hooks. Idempotent --
        a second patch() call does not double-register."""
        from crewai.hooks import register_after_tool_call_hook, register_before_tool_call_hook

        self._client = client
        self._session_id = str(uuid.uuid4())
        self._counter = itertools.count(1)

        if getattr(self, "_registered", False):
            return
        register_before_tool_call_hook(self.on_before_tool_call)
        register_after_tool_call_hook(self.on_after_tool_call)
        self._registered = True

    def on_before_tool_call(self, context: Any) -> bool | None:
        """A before_tool_call hook: return False to block execution, None to
        allow it. context.tool_input is the mutable dict of tool arguments."""
        try:
            _run_sync(self._client.intercept(
                tool_name=context.tool_name,
                tool_parameters=dict(context.tool_input or {}),
                session_id=self._session_id,
                sequence_number=next(self._counter),
            ))
        except (PolicyDeniedError, ReviewPendingError):
            return False
        return None

    def on_after_tool_call(self, context: Any) -> str | None:
        """An after_tool_call hook: advisory only, same reasoning as the
        OpenAI Agents SDK adapter's on_tool_end -- the tool already ran, so
        there is nothing left to block by raising here."""
        _run_sync(self._client.report_response(
            tool_name=context.tool_name,
            tool_response=context.raw_tool_result,
            session_id=self._session_id,
            sequence_number=0,
        ))
        return None

    def extract_usage(self, response: Any) -> dict:
        usage = getattr(response, "token_usage", None) or getattr(response, "usage_metrics", None)
        if usage is None:
            return {}
        return {
            "input_tokens": getattr(usage, "prompt_tokens", 0),
            "output_tokens": getattr(usage, "completion_tokens", 0),
        }
