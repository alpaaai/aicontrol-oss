"""Adapter registry — one FrameworkAdapter instance per supported framework, keyed by name."""
from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter
from aicontrol_sdk.adapters.base import FrameworkAdapter
from aicontrol_sdk.adapters.google_adk import GoogleADKAdapter
from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter

ADAPTER_REGISTRY: dict[str, FrameworkAdapter] = {}


def register(adapter: FrameworkAdapter) -> None:
    ADAPTER_REGISTRY[adapter.name] = adapter


def get(name: str) -> FrameworkAdapter:
    return ADAPTER_REGISTRY[name]


def detect() -> FrameworkAdapter:
    """Return the first registered adapter whose framework package is importable."""
    for adapter in ADAPTER_REGISTRY.values():
        if adapter.is_available():
            return adapter
    raise RuntimeError(
        "No supported agent framework detected. Install one of: "
        "claude-agent-sdk, openai-agents, google-adk — or pass framework= explicitly."
    )


register(AnthropicAgentSDKAdapter())
register(OpenAIAgentsSDKAdapter())
register(GoogleADKAdapter())
