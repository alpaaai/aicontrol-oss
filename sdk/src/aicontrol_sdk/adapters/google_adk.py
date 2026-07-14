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

        class AIControlPlugin(BasePlugin):
            def __init__(self_):
                super().__init__(name="aicontrol")

            async def before_tool_callback(
                self_, *, tool, tool_args: dict, tool_context
            ) -> Optional[dict]:
                session_id = getattr(tool_context, "session_id", None) or getattr(
                    tool_context, "invocation_id", "default"
                )
                counter = session_counters.setdefault(session_id, itertools.count(1))
                try:
                    await client.intercept(
                        tool_name=getattr(tool, "name", str(tool)),
                        tool_parameters=tool_args or {},
                        session_id=session_id,
                        sequence_number=next(counter),
                    )
                except PolicyDeniedError as exc:
                    return {"error": f"Blocked by AIControl policy: {exc.reason}"}
                except ReviewPendingError as exc:
                    return {"error": f"Pending human review: {exc.review_id}"}
                except AIControlUnavailableError:
                    return {"error": "AIControl unavailable"}
                return None

        return AIControlPlugin()

    def extract_usage(self, response: Any) -> dict:
        """No stable per-tool-call usage attribute confirmed on ToolContext — best-effort None."""
        return {}
