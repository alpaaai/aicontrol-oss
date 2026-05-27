"""
AIControl AI Client — single LLM abstraction layer.

ALL AI-native feature calls go through this module. No exceptions.
Never import Anthropic SDK or OpenAI SDK directly in feature code.

Customer provides LLM config via .env — AIControl never handles token billing.
Token budget (max_tokens) is REQUIRED on every call. No default. Enforces discipline.
AICONTROL_LLM_MOCK=true enables mock-first development — no real API calls.
"""
import time
import structlog
from litellm import acompletion
from app.core.config import settings

logger = structlog.get_logger()


class AIClient:

    @staticmethod
    async def complete(
        messages: list[dict],
        max_tokens: int,           # REQUIRED. No default. Define in plan doc.
        system_prompt: str,
        feature_name: str,         # For cost attribution in logs.
        mock_response: str | None = None,
    ) -> str:
        if max_tokens <= 0:
            raise ValueError(
                f"max_tokens must be positive for '{feature_name}'. "
                "Define token budget in plan doc before building."
            )

        if settings.LLM_MOCK_ENABLED:
            logger.info("ai_call_mock", feature=feature_name)
            return mock_response or "MOCK_RESPONSE: LLM_MOCK_ENABLED=true"

        start = time.monotonic()
        response = await acompletion(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                *messages
            ],
            max_tokens=max_tokens,
            api_key=settings.LLM_API_KEY,
        )
        latency_ms = round((time.monotonic() - start) * 1000)
        usage = response.usage

        logger.info(
            "ai_call",
            feature=feature_name,
            model=settings.LLM_MODEL,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            latency_ms=latency_ms,
        )
        return response.choices[0].message.content
