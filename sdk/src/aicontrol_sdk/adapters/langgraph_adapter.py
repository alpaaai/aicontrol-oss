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
"""
import itertools
import uuid
from typing import Any

from aicontrol_sdk.intercept_client import InterceptClient


class LangGraphAdapter:
    name = "langgraph"

    def is_available(self) -> bool:
        try:
            import langgraph  # noqa: F401
            return True
        except ImportError:
            return False

    def patch(self, client: InterceptClient) -> None:
        self._client = client

    def build_callback_handler(self, session_id: str | None = None):
        """Returns a BaseCallbackHandler to pass as config={"callbacks": [...]}
        on graph.invoke()/.ainvoke() calls — LangGraph does not offer a global
        monkeypatch point the way OpenAI Agents SDK's Runner does, so callers
        wire this in explicitly per invocation."""
        from langchain_core.callbacks import BaseCallbackHandler

        client = self._client
        sid = session_id or str(uuid.uuid4())
        counter = itertools.count(1)
        run_id_to_tool_name: dict[Any, str] = {}

        class AIControlCallbackHandler(BaseCallbackHandler):
            async def on_tool_start(self_, serialized, input_str, *, run_id, **kwargs):
                tool_name = serialized.get("name", "unknown")
                run_id_to_tool_name[run_id] = tool_name
                await client.intercept(
                    tool_name=tool_name,
                    tool_parameters=kwargs.get("inputs") or {},
                    session_id=sid,
                    sequence_number=next(counter),
                )

            async def on_tool_end(self_, output, *, run_id, **kwargs):
                tool_name = run_id_to_tool_name.pop(run_id, "unknown")
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
