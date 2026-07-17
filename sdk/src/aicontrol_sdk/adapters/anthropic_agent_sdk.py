"""Adapter for Anthropic's Claude Agent SDK (claude-agent-sdk).

Uses a PreToolUse hook rather than the SDK's `can_use_tool` callback: the SDK
warns that `can_use_tool` is shadowed (never invoked) for tool calls already
permitted by `allowed_tools`/`permission_mode`, so it cannot guarantee every
tool call is governed. PreToolUse hooks fire unconditionally.
"""
import itertools
from typing import Any

from aicontrol_sdk.exceptions import AIControlUnavailableError, PolicyDeniedError, ReviewPendingError
from aicontrol_sdk.intercept_client import InterceptClient


class AnthropicAgentSDKAdapter:
    name = "anthropic"

    def is_available(self) -> bool:
        try:
            import claude_agent_sdk  # noqa: F401
            return True
        except ImportError:
            return False

    def patch(self, client: InterceptClient) -> None:
        """Monkeypatch ClaudeAgentOptions.__init__ so any options instance
        constructed after this call automatically has AIControl's PreToolUse
        HookMatcher registered. Callers who already add their own PreToolUse
        hooks keep them too. Idempotent -- a second patch() call is a no-op.

        Also monkeypatches ClaudeSDKClient.receive_messages and the
        module-level query() so real per-turn token usage (AssistantMessage.usage
        -- no model-call hook exists in this SDK, see extract_usage()'s
        docstring) is tapped off the message stream and attached to the
        following tool call, same as the other two adapters' model-call
        hooks -- see _wrap_message_stream()."""
        self._client = client
        self._usage_accumulators: dict[str, dict] = {}
        import claude_agent_sdk
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

        # Always wrap the TRUE originals (captured once, on the first
        # patch() call ever) rather than whatever they currently are --
        # patching a second time would otherwise wrap an already-patched
        # version, stacking duplicate hook injection on every call.
        if not hasattr(ClaudeAgentOptions, "_aicontrol_original_init"):
            ClaudeAgentOptions._aicontrol_original_init = ClaudeAgentOptions.__init__
        if not hasattr(ClaudeSDKClient, "_aicontrol_original_receive_messages"):
            ClaudeSDKClient._aicontrol_original_receive_messages = ClaudeSDKClient.receive_messages
        if not hasattr(claude_agent_sdk, "_aicontrol_original_query"):
            claude_agent_sdk._aicontrol_original_query = claude_agent_sdk.query

        adapter = self
        original_init = ClaudeAgentOptions._aicontrol_original_init
        original_receive_messages = ClaudeSDKClient._aicontrol_original_receive_messages
        original_query = claude_agent_sdk._aicontrol_original_query

        def patched_init(self_, *args, **kwargs):
            original_init(self_, *args, **kwargs)
            matcher = adapter.build_hook_matcher()
            if self_.hooks is None:
                self_.hooks = {}
            self_.hooks.setdefault("PreToolUse", []).append(matcher)

        def patched_receive_messages(self_):
            return adapter._wrap_message_stream(original_receive_messages(self_))

        def patched_query(*args, **kwargs):
            return adapter._wrap_message_stream(original_query(*args, **kwargs))

        ClaudeAgentOptions.__init__ = patched_init
        ClaudeSDKClient.receive_messages = patched_receive_messages
        claude_agent_sdk.query = patched_query

    async def _wrap_message_stream(self, message_stream):
        """Taps AssistantMessage.usage off an async iterator of SDK messages,
        accumulating per session_id into self._usage_accumulators, and yields
        every message through unchanged -- a pure observation point, never
        altering, dropping, or delaying a message. Wraps both
        ClaudeSDKClient.receive_messages and the module-level query(), the
        only two places AssistantMessage instances are produced. The
        accumulated usage is drained by build_hook_matcher()'s PreToolUse
        hook on the next tool call for that session, exactly like
        on_tool_start/before_tool_callback do in the other two adapters."""
        from claude_agent_sdk import AssistantMessage

        async for message in message_stream:
            if isinstance(message, AssistantMessage):
                session_id = message.session_id or "default"
                usage = self.extract_usage(message)
                if usage:
                    acc = self._usage_accumulators.setdefault(
                        session_id, {"input_tokens": 0, "output_tokens": 0}
                    )
                    acc["input_tokens"] += usage.get("input_tokens", 0)
                    acc["output_tokens"] += usage.get("output_tokens", 0)
            yield message

    def build_hook_matcher(self):
        """Build a HookMatcher wired to intercept every PreToolUse event.

        Call this after patch() and append the result to
        `ClaudeAgentOptions.hooks["PreToolUse"]`.
        """
        from claude_agent_sdk import HookMatcher

        client = self._client
        usage_accumulators = self._usage_accumulators
        session_counters: dict[str, itertools.count] = {}

        async def _hook(input_data, tool_use_id, context):
            session_id = input_data.get("session_id", "default")
            counter = session_counters.setdefault(session_id, itertools.count(1))
            # Read-and-reset: usage from the AssistantMessage(s) that preceded
            # this tool call attaches here. Same one-tool-call lag and
            # accumulate-then-drain behavior as the other two adapters'
            # on_tool_start/before_tool_callback.
            acc = usage_accumulators.get(session_id)
            input_tokens = (acc["input_tokens"] or None) if acc else None
            output_tokens = (acc["output_tokens"] or None) if acc else None
            if acc:
                acc["input_tokens"] = 0
                acc["output_tokens"] = 0
            try:
                await client.intercept(
                    tool_name=input_data["tool_name"],
                    tool_parameters=input_data.get("tool_input", {}),
                    session_id=session_id,
                    sequence_number=next(counter),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            except PolicyDeniedError as exc:
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": exc.reason,
                    }
                }
            except ReviewPendingError as exc:
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"human_review_pending:{exc.review_id}",
                    }
                }
            except AIControlUnavailableError:
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "aicontrol_unavailable",
                    }
                }
            return {}

        return HookMatcher(hooks=[_hook])

    def build_post_tool_hook_matcher(self):
        """Build a HookMatcher for PostToolUse -- reports the real tool
        response back for scanning (app/services/response_scanner.py via
        POST /intercept/report-response), and can suppress unsafe output
        via PostToolUseHookSpecificOutput.updatedToolOutput before it
        re-enters the model's context.
        """
        from claude_agent_sdk import HookMatcher

        client = self._client

        async def _hook(input_data, tool_use_id, context):
            session_id = input_data.get("session_id", "default")
            result = await client.report_response(
                tool_name=input_data["tool_name"],
                tool_response=input_data.get("tool_response"),
                session_id=session_id,
                sequence_number=0,
            )
            if result.get("decision") == "deny":
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "updatedToolOutput": {"error": f"Blocked by AIControl: {result.get('reason')}"},
                    }
                }
            return {}

        return HookMatcher(hooks=[_hook])

    def extract_usage(self, response: Any) -> dict:
        """Pulls real per-turn token counts off an AssistantMessage.usage dict
        (the raw Anthropic Messages API usage object -- dict access, not
        attribute access, since AssistantMessage.usage is typed as
        dict[str, Any] | None). Called internally by the wrapped
        receive_messages()/query() generators as each AssistantMessage passes
        through -- not part of the public patch() flow."""
        usage = getattr(response, "usage", None)
        if not usage:
            return {}
        return {"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0)}
