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
        """Build a RunHooks instance to pass as `Runner.run(..., hooks=...)`.

        Usage accumulator is closed over here (not a module/instance-level
        dict keyed by session_id) so it is automatically scoped to this one
        run and can never leak into a concurrent run's usage -- build_hooks()
        is called fresh per Runner.run()/run_sync()/run_streamed() call."""
        from agents.lifecycle import RunHooksBase

        client = self._client
        counter = itertools.count(1)
        usage_accumulator = {"input_tokens": 0, "output_tokens": 0}

        class AIControlHooks(RunHooksBase):
            async def on_llm_end(self_, context, agent, response) -> None:
                """Fires once per LLM call (not once per run). Accumulates
                rather than overwrites: on_llm_end can fire more than once
                before the next tool call (e.g. the SDK retrying a failed
                model call internally), and a retried call's real spend
                must not be discarded."""
                usage = self.extract_usage(response)
                usage_accumulator["input_tokens"] += usage.get("input_tokens", 0)
                usage_accumulator["output_tokens"] += usage.get("output_tokens", 0)

            async def on_tool_start(self_, context, agent, tool) -> None:
                """Reads and resets the accumulator: usage from the LLM call
                that decided on this tool attaches here. When one LLM call
                produces multiple parallel tool calls, only the first
                on_tool_start in that batch sees non-zero usage -- the
                accumulator is already drained by the time the second one
                fires, since there was no second LLM call to refill it.
                This is a deliberate simplification (usage isn't split or
                repeated across a parallel batch), not an oversight."""
                input_tokens = usage_accumulator["input_tokens"] or None
                output_tokens = usage_accumulator["output_tokens"] or None
                usage_accumulator["input_tokens"] = 0
                usage_accumulator["output_tokens"] = 0
                await client.intercept(
                    tool_name=getattr(tool, "name", str(tool)),
                    tool_parameters=getattr(context, "tool_arguments", {}) or {},
                    session_id=session_id,
                    sequence_number=next(counter),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

            async def on_tool_end(self_, context, agent, tool, result: object) -> None:
                """on_tool_end has no blocking return value (pure lifecycle
                notification, same limitation as on_tool_start's own
                docstring already notes) -- a flagged response cannot be
                suppressed here, only detected and audited. Raising would
                abort the whole run, which is too blunt for an advisory
                scan; this reports and logs only."""
                await client.report_response(
                    tool_name=getattr(tool, "name", str(tool)),
                    tool_response=result,
                    session_id=session_id,
                    sequence_number=0,
                )

        return AIControlHooks()

    def extract_usage(self, response: Any) -> dict:
        """Pulls real per-call token counts off a ModelResponse.usage
        (agents.usage.Usage), as handed to on_llm_end. Called internally by
        build_hooks()'s on_llm_end -- not part of the public patch() flow."""
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        return {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}
