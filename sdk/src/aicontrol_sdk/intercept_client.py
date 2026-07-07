"""httpx client for POST /intercept, with fail-open/closed handling."""
import uuid
from typing import Any, Optional

import httpx

from aicontrol_sdk.config import Config
from aicontrol_sdk.exceptions import AIControlUnavailableError, PolicyDeniedError, ReviewPendingError


class InterceptClient:
    def __init__(self, config: Config, transport: Optional[httpx.BaseTransport] = None):
        self._config = config
        self._client = httpx.AsyncClient(base_url=config.url, transport=transport, timeout=5.0)

    async def intercept(
        self,
        tool_name: str,
        tool_parameters: dict[str, Any],
        session_id: str,
        sequence_number: int,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        cost_usd: Optional[float] = None,
    ) -> dict:
        """POST /intercept. Raises PolicyDeniedError/ReviewPendingError on deny/review.

        On connection failure: fail_mode="deny" raises AIControlUnavailableError;
        fail_mode="allow" returns a synthetic allow decision.
        """
        body: dict[str, Any] = {
            "session_id": session_id,
            "agent_id": self._config.agent_id,
            "agent_name": self._config.agent_name,
            "tool_name": tool_name,
            "tool_parameters": tool_parameters,
            "sequence_number": sequence_number,
        }
        if input_tokens is not None:
            body["input_tokens"] = input_tokens
        if output_tokens is not None:
            body["output_tokens"] = output_tokens
        if cost_usd is not None:
            body["cost_usd"] = cost_usd

        try:
            response = await self._client.post(
                "/intercept",
                headers={"Authorization": f"Bearer {self._config.token}"},
                json=body,
            )
        except httpx.HTTPError as exc:
            if self._config.fail_mode == "allow":
                return {"decision": "allow", "reason": "aicontrol_unavailable_fail_open"}
            raise AIControlUnavailableError(cause=exc) from exc

        response.raise_for_status()
        result = response.json()

        if result["decision"] == "deny":
            raise PolicyDeniedError(reason=result["reason"], policy_name=result.get("policy_name"))
        if result["decision"] == "review":
            raise ReviewPendingError(review_id=result["review_id"])

        return result

    async def aclose(self) -> None:
        await self._client.aclose()
