"""Adapter for the OpenAI Agents SDK (openai-agents).

RunHooksBase.on_tool_start/on_tool_end are pure lifecycle notifications (no
blocking return value) — so this adapter blocks a denied/review call by
raising PolicyDeniedError/ReviewPendingError directly from on_tool_start,
which aborts the run before the tool executes.
"""
import itertools
from typing import Any

from aicontrol_sdk.intercept_client import InterceptClient


class OpenAIAgentsSDKAdapter:
    name = "openai_agents"

    def is_available(self) -> bool:
        try:
            import agents  # noqa: F401
            return True
        except ImportError:
            return False

    def patch(self, client: InterceptClient) -> None:
        """Monkeypatch agents.Runner.run/run_sync/run_streamed so any call that
        doesn't explicitly pass its own hooks= gets AIControl's hooks injected
        automatically. Callers who pass their own hooks= are left untouched.
        Idempotent -- a second patch() call is a no-op."""
        self._client = client
        import uuid
        import agents

        # Always wrap the TRUE originals (captured once, on the first patch()
        # call ever) rather than whatever Runner.run/etc. currently are --
        # patching a second time would otherwise wrap an already-patched
        # version, stacking duplicate hook injection on every call.
        if not hasattr(agents.Runner, "_aicontrol_original_run"):
            agents.Runner._aicontrol_original_run = agents.Runner.run.__func__
            agents.Runner._aicontrol_original_run_sync = agents.Runner.run_sync.__func__
            agents.Runner._aicontrol_original_run_streamed = agents.Runner.run_streamed.__func__

        adapter = self
        original_run = agents.Runner._aicontrol_original_run
        original_run_sync = agents.Runner._aicontrol_original_run_sync
        original_run_streamed = agents.Runner._aicontrol_original_run_streamed

        async def patched_run(cls, *args, **kwargs):
            if kwargs.get("hooks") is None:
                kwargs["hooks"] = adapter.build_hooks(session_id=str(uuid.uuid4()))
            return await original_run(cls, *args, **kwargs)

        def patched_run_sync(cls, *args, **kwargs):
            if kwargs.get("hooks") is None:
                kwargs["hooks"] = adapter.build_hooks(session_id=str(uuid.uuid4()))
            return original_run_sync(cls, *args, **kwargs)

        def patched_run_streamed(cls, *args, **kwargs):
            if kwargs.get("hooks") is None:
                kwargs["hooks"] = adapter.build_hooks(session_id=str(uuid.uuid4()))
            return original_run_streamed(cls, *args, **kwargs)

        agents.Runner.run = classmethod(patched_run)
        agents.Runner.run_sync = classmethod(patched_run_sync)
        agents.Runner.run_streamed = classmethod(patched_run_streamed)

    def build_hooks(self, session_id: str):
        """Build a RunHooks instance to pass as `Runner.run(..., hooks=...)`."""
        from agents.lifecycle import RunHooksBase

        client = self._client
        counter = itertools.count(1)

        class AIControlHooks(RunHooksBase):
            async def on_tool_start(self_, context, agent, tool) -> None:
                await client.intercept(
                    tool_name=getattr(tool, "name", str(tool)),
                    tool_parameters=getattr(context, "tool_arguments", {}) or {},
                    session_id=session_id,
                    sequence_number=next(counter),
                )

        return AIControlHooks()

    def extract_usage(self, response: Any) -> dict:
        """Usage is tracked at the RunResult level in this SDK, not per tool call."""
        return {}
