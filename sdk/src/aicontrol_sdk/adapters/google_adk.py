"""Adapter for Google's Agent Development Kit (google-adk).

Implements google.adk.plugins.base_plugin.BasePlugin.before_tool_callback:
returning a dict short-circuits tool execution and uses that dict as the
tool's result — this is ADK's blocking mechanism (not an exception).
"""
import itertools
from typing import Any, Optional

from aicontrol_sdk.exceptions import AIControlUnavailableError, PolicyDeniedError, ReviewPendingError
from aicontrol_sdk.intercept_client import InterceptClient


class GoogleADKAdapter:
    name = "google_adk"

    def is_available(self) -> bool:
        try:
            import google.adk.plugins.base_plugin  # noqa: F401
            return True
        except ImportError:
            return False

    def patch(self, client: InterceptClient) -> None:
        """Monkeypatch google.adk.runners.Runner.__init__ so any Runner
        constructed after this call automatically has AIControl's plugin
        registered. Callers who already pass their own plugins list keep it
        too. Idempotent -- a second patch() call is a no-op."""
        self._client = client
        from google.adk.runners import Runner

        # Always wrap the TRUE original __init__ (captured once, on the first
        # patch() call ever) rather than whatever __init__ currently is --
        # patching a second time would otherwise wrap an already-patched
        # __init__, stacking duplicate plugins on every subsequent Runner.
        if not hasattr(Runner, "_aicontrol_original_init"):
            Runner._aicontrol_original_init = Runner.__init__

        adapter = self
        original_init = Runner._aicontrol_original_init

        def patched_init(self_, *args, **kwargs):
            plugins = list(kwargs.get("plugins") or [])
            plugins.append(adapter.build_plugin())
            kwargs["plugins"] = plugins
            original_init(self_, *args, **kwargs)

        Runner.__init__ = patched_init

    def build_plugin(self):
        """Build a BasePlugin subclass instance to pass to the ADK Runner's plugins list."""
        from google.adk.plugins.base_plugin import BasePlugin

        client = self._client
        session_counters: dict[str, itertools.count] = {}
        usage_accumulators: dict[str, dict] = {}

        class AIControlPlugin(BasePlugin):
            def __init__(self_):
                super().__init__(name="aicontrol")

            async def after_model_callback(self_, *, callback_context, llm_response) -> None:
                """Fires once per LLM call. Accumulates rather than
                overwrites -- see build_hooks() in the OpenAI adapter for
                why (retried model calls must not have their usage
                discarded). Keyed by session_id, same pattern as
                session_counters above, since this plugin instance is
                shared across a Runner's sessions."""
                session_id = getattr(callback_context, "session_id", None) or getattr(
                    callback_context, "invocation_id", "default"
                )
                usage = self.extract_usage(llm_response)
                acc = usage_accumulators.setdefault(session_id, {"input_tokens": 0, "output_tokens": 0})
                acc["input_tokens"] += usage.get("input_tokens", 0)
                acc["output_tokens"] += usage.get("output_tokens", 0)

            async def before_tool_callback(
                self_, *, tool, tool_args: dict, tool_context
            ) -> Optional[dict]:
                session_id = getattr(tool_context, "session_id", None) or getattr(
                    tool_context, "invocation_id", "default"
                )
                counter = session_counters.setdefault(session_id, itertools.count(1))
                acc = usage_accumulators.setdefault(session_id, {"input_tokens": 0, "output_tokens": 0})
                input_tokens = acc["input_tokens"] or None
                output_tokens = acc["output_tokens"] or None
                acc["input_tokens"] = 0
                acc["output_tokens"] = 0
                try:
                    await client.intercept(
                        tool_name=getattr(tool, "name", str(tool)),
                        tool_parameters=tool_args or {},
                        session_id=session_id,
                        sequence_number=next(counter),
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )
                except PolicyDeniedError as exc:
                    return {"error": f"Blocked by AIControl policy: {exc.reason}"}
                except ReviewPendingError as exc:
                    return {"error": f"Pending human review: {exc.review_id}"}
                except AIControlUnavailableError:
                    return {"error": "AIControl unavailable"}
                return None

            async def after_tool_callback(
                self_, *, tool, tool_args: dict, tool_context, result: dict
            ) -> Optional[dict]:
                session_id = getattr(tool_context, "session_id", None) or getattr(
                    tool_context, "invocation_id", "default"
                )
                report = await client.report_response(
                    tool_name=getattr(tool, "name", str(tool)),
                    tool_response=result,
                    session_id=session_id,
                    sequence_number=0,
                )
                if report.get("decision") == "deny":
                    return {"error": f"Blocked by AIControl: {report.get('reason')}"}
                return None

        return AIControlPlugin()

    def extract_usage(self, response: Any) -> dict:
        """Pulls real per-call token counts off an LlmResponse.usage_metadata
        (google.genai.types.GenerateContentResponseUsageMetadata), as handed
        to after_model_callback. Called internally by build_plugin()'s
        after_model_callback — not part of the public patch() flow."""
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata is None:
            return {}
        return {
            "input_tokens": usage_metadata.prompt_token_count or 0,
            "output_tokens": usage_metadata.candidates_token_count or 0,
        }
