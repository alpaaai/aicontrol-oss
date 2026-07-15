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
        hooks keep them too. Idempotent -- a second patch() call is a no-op."""
        self._client = client
        from claude_agent_sdk import ClaudeAgentOptions

        # Always wrap the TRUE original __init__ (captured once, on the first
        # patch() call ever) rather than whatever __init__ currently is --
        # patching a second time would otherwise wrap an already-patched
        # __init__, stacking duplicate hooks on every subsequent instance.
        if not hasattr(ClaudeAgentOptions, "_aicontrol_original_init"):
            ClaudeAgentOptions._aicontrol_original_init = ClaudeAgentOptions.__init__

        adapter = self
        original_init = ClaudeAgentOptions._aicontrol_original_init

        def patched_init(self_, *args, **kwargs):
            original_init(self_, *args, **kwargs)
            matcher = adapter.build_hook_matcher()
            if self_.hooks is None:
                self_.hooks = {}
            self_.hooks.setdefault("PreToolUse", []).append(matcher)

        ClaudeAgentOptions.__init__ = patched_init

    def build_hook_matcher(self):
        """Build a HookMatcher wired to intercept every PreToolUse event.

        Call this after patch() and append the result to
        `ClaudeAgentOptions.hooks["PreToolUse"]`.
        """
        from claude_agent_sdk import HookMatcher

        client = self._client
        session_counters: dict[str, itertools.count] = {}

        async def _hook(input_data, tool_use_id, context):
            session_id = input_data.get("session_id", "default")
            counter = session_counters.setdefault(session_id, itertools.count(1))
            try:
                await client.intercept(
                    tool_name=input_data["tool_name"],
                    tool_parameters=input_data.get("tool_input", {}),
                    session_id=session_id,
                    sequence_number=next(counter),
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
        """ResultMessage.usage/total_cost_usd are session-level, not per-tool-call —
        no reliable per-call usage source for this adapter."""
        return {}
