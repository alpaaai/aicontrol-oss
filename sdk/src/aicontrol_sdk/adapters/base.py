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
        object (e.g. ModelResponse, LlmResponse). Called internally by the
        adapter's own model-call hook (on_llm_end, after_model_callback) to
        feed the accumulator that on_tool_start/before_tool_callback reads
        from — not called directly by patch() or any external caller.

        Returns a dict with any subset of input_tokens/output_tokens keys.
        Frameworks with no model-call-level hook (e.g. Claude Agent SDK, as
        of this writing) return {} — there is no response object to extract
        from without one.
        """
        ...
