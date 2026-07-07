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
        self._client = client

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
