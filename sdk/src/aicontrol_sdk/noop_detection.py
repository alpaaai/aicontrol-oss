"""Detect configurations in which the governance check is installed but never fires.

Static inspection of the object the adapter just wrapped. Never a synthetic
tool call: a fake call would pollute the audit trail and need a per-framework
injection harness, for information this inspection already yields.

Findings travel on the coverage handshake and surface on the agent in the
dashboard. The LangChain sync-tool case has no adapter-side fix -- disclosing
it by name is the only honest handling.

Keys are adapter `name` values (FrameworkAdapter.name), so an adapter can pass
its own name straight in.
"""
import inspect
import logging
from typing import Any

logger = logging.getLogger("aicontrol_sdk.noop_detection")


def _anthropic(target: Any) -> list[str]:
    can_use_tool = getattr(target, "can_use_tool", None)
    allowed_tools = getattr(target, "allowed_tools", None)
    if can_use_tool is not None and allowed_tools:
        return [
            "allowed_tools_shadows_can_use_tool: allowed_tools short-circuits "
            "the can_use_tool callback, so no tool call reaches AIControl"
        ]
    return []


def _openai(target: Any) -> list[str]:
    warnings = []
    for tool in getattr(target, "tools", None) or []:
        if not getattr(tool, "__aicontrol_function_tool__", False):
            name = getattr(tool, "name", repr(tool))
            warnings.append(
                f"tool_not_function_tool:{name} - OpenAI tool guardrails only "
                "fire on tools defined via function_tool"
            )
    return warnings


def _langgraph(target: Any) -> list[str]:
    warnings = []
    for tool in getattr(target, "tools", None) or []:
        func = getattr(tool, "func", None)
        if func is not None and not inspect.iscoroutinefunction(func):
            name = getattr(tool, "name", repr(tool))
            warnings.append(
                f"sync_tool_denial_swallowed:{name} - LangChain's callback "
                "manager swallows the denial for sync-defined tools and the "
                "tool runs. Define the tool `async def`; no adapter-side fix exists."
            )
    return warnings


_DETECTORS = {
    "anthropic": _anthropic,
    "openai_agents": _openai,
    "langgraph": _langgraph,
}


def detect_silent_noop(framework: str, target: Any) -> list[str]:
    """Return a list of human-readable warnings, empty when the binding is sound.

    Never raises. This runs at import time inside the host application, and a
    governance library must not be the reason an application fails to start.
    """
    detector = _DETECTORS.get(framework)
    if detector is None:
        return []
    try:
        return detector(target)
    except Exception as exc:
        logger.warning("noop_detection_failed framework=%s error=%s", framework, exc)
        return []
