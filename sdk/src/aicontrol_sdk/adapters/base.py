"""FrameworkAdapter protocol — one adapter per supported agent framework."""
from typing import Any, Protocol

from aicontrol_sdk.intercept_client import InterceptClient


class FrameworkAdapter(Protocol):
    name: str

    def is_available(self) -> bool:
        """Whether this framework's package is importable in the current environment."""
        ...

    def patch(self, client: InterceptClient) -> None:
        """Wire this framework's tool-execution lifecycle to call client.intercept()."""
        ...

    def extract_usage(self, response: Any) -> dict:
        """Pulls real per-LLM-call token usage off a raw framework response
        or message object (e.g. ModelResponse, LlmResponse, AssistantMessage).
        Called internally by the adapter's own usage-capture tap to feed the
        accumulator that the tool-execution hook reads from — not called
        directly by patch() or any external caller.

        Returns a dict with any subset of input_tokens/output_tokens keys, or
        {} if the object carries no usage. The capture point differs per
        framework: OpenAI Agents and Google ADK call this from a
        framework-invoked model-call hook (on_llm_end, after_model_callback).
        The Claude Agent SDK has no such hook — instead its adapter taps
        AssistantMessage instances off the message stream
        (ClaudeSDKClient.receive_messages / query()), the only place per-turn
        usage appears in that SDK. All three route through this same method
        and feed the same accumulate-then-drain-on-next-tool-call pattern.
        """
        ...
