"""Adapter for LangGraph (langgraph + langchain_core's BaseCallbackHandler).

Unlike the OpenAI Agents SDK / Google ADK adapters, LangGraph has no single
global entrypoint (like `Runner.run`) to monkeypatch — confirmed this
session by reading the installed langgraph package: there is no equivalent
of a global handler registry. `patch()` only stores the client; callers must
pass `build_callback_handler()`'s result into their own
`graph.invoke(config={"callbacks": [...]})` / `.ainvoke(...)` call.

`on_tool_start`/`on_tool_end` signatures confirmed against the installed
langchain_core.callbacks.base.BaseCallbackHandler source: `on_tool_start`
receives `serialized={"name": ..., "description": ...}` and `inputs=`, but
`on_tool_end` receives only `output` and `run_id` — no tool name. This
adapter tracks run_id -> tool_name (set in on_tool_start, popped in
on_tool_end) to report the correct name in report_response.

KNOWN LIMITATION -- blocking only holds for async-defined tools
(`@tool async def ...` / a `BaseTool` implementing `_arun`). Confirmed
against installed langchain_core.callbacks.manager source: a sync tool
(only `_run` implemented) fires `on_tool_start` through the SYNC
`CallbackManager.handle_event`, which calls the (async) handler method to
get a coroutine object, queues it, and runs it later via `_run_coros` --
whose exceptions are "always logged and swallowed here, regardless of the
handler's raise_error setting" (LangChain's own comment,
callbacks/manager.py). `raise_error = True` below only takes effect on the
ASYNC path (`_ahandle_event_for_handler`, used when the tool's own
execution is async), which the handler's on_tool_start coroutine runs on
directly rather than being queued. Confirmed empirically this session:
identical deny scenario, only the tool's sync-vs-async definition differs
-- async tool call was blocked, sync tool call executed anyway despite the
same deny decision and the same raise_error=True handler. There is no
workaround from this adapter's side; integrators who need a governance
deny to actually block LangGraph tool execution must define tools with
`async def`, not plain `def`.
"""
import itertools
import logging
import uuid
from typing import Any

from aicontrol_sdk.adapters.base import CoverageReporting, WorkflowResolution
from aicontrol_sdk.intercept_client import InterceptClient

logger = logging.getLogger("aicontrol_sdk.langgraph")


class LangGraphAdapter(WorkflowResolution, CoverageReporting):
    name = "langgraph"
    hook = "BaseCallbackHandler.on_tool_start"

    def is_available(self) -> bool:
        try:
            import langgraph  # noqa: F401
            return True
        except ImportError:
            return False

    def patch(self, client: InterceptClient, workflow: str | None = None,
              target: Any = None) -> None:
        """`target` is the compiled graph, when the caller has one: it is what
        the sync-tool detection inspects, and what carries the graph name."""
        self._client = client
        self._declared_workflow = workflow
        if target is not None:
            self.capture_framework_workflow(target)
        self.report_coverage(client, target=target)

    def resolve_session_id(self, *, thread_id: str | None, run_id: Any = None) -> str:
        """thread_id is LangGraph's conversation: it is stable across the turns
        of one thread, which is what a session means here. run_id identifies a
        single invocation and is the next best thing. Generating one is the
        last resort -- it correlates with nothing on the LangGraph side."""
        if thread_id:
            return str(thread_id)
        if run_id:
            return str(run_id)
        logger.warning("langgraph_session_id_generated_no_framework_id")
        return str(uuid.uuid4())

    def session_id_from_config(self, config: Any, run_id: Any = None) -> str:
        """The callback receives the run config (and, on newer langchain_core,
        a metadata dict carrying the same thread_id). Read either shape."""
        configurable = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
        thread_id = configurable.get("thread_id") or (
            (config or {}).get("thread_id") if isinstance(config, dict) else None
        )
        return self.resolve_session_id(thread_id=thread_id, run_id=run_id)

    def capture_framework_workflow(self, graph: Any) -> None:
        """LangGraph's own name for a process is the compiled graph's name
        (`assistant_id` on a deployed graph, `name` on a locally compiled
        one). "LangGraph" is the default StateGraph name and identifies
        nothing, so it is treated as absent."""
        name = getattr(graph, "assistant_id", None) or getattr(graph, "name", None)
        if name and name != "LangGraph":
            self._framework_workflow = name

    def build_callback_handler(self, session_id: str | None = None, graph: Any = None):
        """Returns a BaseCallbackHandler to pass as config={"callbacks": [...]}
        on graph.invoke()/.ainvoke() calls — LangGraph does not offer a global
        monkeypatch point the way OpenAI Agents SDK's Runner does, so callers
        wire this in explicitly per invocation."""
        from langchain_core.callbacks import BaseCallbackHandler

        if graph is not None:
            self.capture_framework_workflow(graph)

        client = self._client
        adapter = self
        counter = itertools.count(1)
        run_id_to_tool_name: dict[Any, str] = {}
        run_id_to_session_id: dict[Any, str] = {}

        def _session_for(run_id, kwargs) -> str:
            """One handler can serve many threads, so the session is taken
            from the callback's own metadata rather than fixed when the
            handler was built. An explicit session_id= still wins, for
            callers who correlate sessions themselves."""
            if session_id:
                return session_id
            metadata = kwargs.get("metadata") or {}
            return adapter.session_id_from_config(metadata, run_id=run_id)

        class AIControlCallbackHandler(BaseCallbackHandler):
            # LangChain's CallbackManager swallows exceptions raised from
            # callback methods by default (logs a warning and continues) --
            # raise_error=True is the documented opt-out, required here so a
            # policy deny/review actually aborts the tool call instead of
            # only being logged.
            raise_error = True

            async def on_tool_start(self_, serialized, input_str, *, run_id, **kwargs):
                tool_name = serialized.get("name", "unknown")
                run_id_to_tool_name[run_id] = tool_name
                sid = _session_for(run_id, kwargs)
                run_id_to_session_id[run_id] = sid
                await client.intercept(
                    tool_name=tool_name,
                    tool_parameters=kwargs.get("inputs") or {},
                    session_id=sid,
                    sequence_number=next(counter),
                    workflow=adapter.resolve_workflow(),
                )

            async def on_tool_end(self_, output, *, run_id, **kwargs):
                tool_name = run_id_to_tool_name.pop(run_id, "unknown")
                # Same session the matching on_tool_start reported under --
                # on_tool_end carries no metadata to re-derive it from.
                sid = run_id_to_session_id.pop(run_id, None) or _session_for(run_id, kwargs)
                await client.report_response(
                    tool_name=tool_name,
                    tool_response=output,
                    session_id=sid,
                    sequence_number=0,
                )

        return AIControlCallbackHandler()

    def extract_usage(self, response: Any) -> dict:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return {}
        return {"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0)}
