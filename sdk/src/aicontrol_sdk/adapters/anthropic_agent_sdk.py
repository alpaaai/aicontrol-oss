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
        """Register a PreToolUse HookMatcher on ClaudeAgentOptions.hooks.

        Usage (in the caller's code, after instrument() has been called):
            options.hooks.setdefault("PreToolUse", []).append(
                get_hook_matcher()
            )
        Exposed as `self.build_hook_matcher(client)` since ClaudeAgentOptions
        is constructed by the caller, not the SDK — there is no global
        "patch every future instance" hook point in claude-agent-sdk.
        """
        self._client = client

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

    def extract_usage(self, response: Any) -> dict:
        """ResultMessage.usage/total_cost_usd are session-level, not per-tool-call —
        no reliable per-call usage source for this adapter."""
        return {}
