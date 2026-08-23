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

from aicontrol_sdk.adapters.base import CoverageReporting, WorkflowResolution
from aicontrol_sdk.exceptions import PolicyDeniedError, ReviewPendingError
from aicontrol_sdk.intercept_client import InterceptClient


def _run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class CrewAIAdapter(WorkflowResolution, CoverageReporting):
    name = "crewai"
    hook = "crewai.hooks.before_tool_call"

    def is_available(self) -> bool:
        try:
            import crewai  # noqa: F401
            return True
        except ImportError:
            return False

    def patch(self, client: InterceptClient, workflow: str | None = None,
              target: Any = None) -> None:
        """Registers process-global before/after tool-call hooks. Idempotent --
        a second patch() call does not double-register."""
        from crewai.hooks import register_after_tool_call_hook, register_before_tool_call_hook

        self._client = client
        self._declared_workflow = workflow
        # Not assigned here: a session id fixed at patch() time makes every
        # run of a long-lived adapter share one session, which reads as a
        # single endless conversation. It is minted per kickoff instead.
        self._session_id = None
        self._counter = itertools.count(1)

        if getattr(self, "_registered", False):
            self.report_coverage(client, target=target)
            return
        register_before_tool_call_hook(self.on_before_tool_call)
        register_after_tool_call_hook(self.on_after_tool_call)
        self._subscribe_to_kickoff()
        self._registered = True
        self.report_coverage(client, target=target)

    def _subscribe_to_kickoff(self) -> None:
        """CrewAI exposes no per-run conversation id, so one is generated --
        but per kickoff. CrewKickoffStartedEvent is the only boundary the
        framework publishes; without it every run of one adapter instance
        would share a session."""
        try:
            from crewai.events import CrewKickoffStartedEvent, crewai_event_bus
        except ImportError:  # older crewai without the events package
            return

        adapter = self

        @crewai_event_bus.on(CrewKickoffStartedEvent)
        def _on_kickoff(source, event) -> None:  # noqa: ARG001
            adapter.start_kickoff()

    def new_session_id(self) -> str:
        return str(uuid.uuid4())

    def start_kickoff(self) -> None:
        """Begin a new session. Called on CrewKickoffStartedEvent."""
        self._session_id = self.new_session_id()
        self._counter = itertools.count(1)

    def current_session_id(self) -> str:
        """The session every tool call in the current kickoff reports under.
        Minted lazily so a tool call that arrives without a kickoff event
        (a directly-executed agent, say) still lands in one session."""
        if getattr(self, "_session_id", None) is None:
            self._session_id = self.new_session_id()
        return self._session_id

    def capture_framework_workflow(self, context: Any) -> None:
        """CrewAI's own name for a process is the crew's name. The hook
        context carries the crew when one is running; a crew constructed
        without a name has none, and the declared workflow is used."""
        crew = getattr(context, "crew", None)
        name = getattr(crew, "name", None)
        if name:
            self._framework_workflow = name

    def on_before_tool_call(self, context: Any) -> bool | None:
        """A before_tool_call hook: return False to block execution, None to
        allow it. context.tool_input is the mutable dict of tool arguments."""
        self.capture_framework_workflow(context)
        try:
            _run_sync(self._client.intercept(
                tool_name=context.tool_name,
                tool_parameters=dict(context.tool_input or {}),
                session_id=self.current_session_id(),
                sequence_number=next(self._counter),
                workflow=self.resolve_workflow(),
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
            session_id=self.current_session_id(),
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
