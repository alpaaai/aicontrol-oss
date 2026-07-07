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
        """Best-effort token/cost usage from a framework response object.

        Returns a dict with any subset of input_tokens/output_tokens/cost_usd keys.
        Frameworks that don't expose per-call usage return {}.
        """
        ...
