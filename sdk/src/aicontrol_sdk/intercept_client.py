"""httpx client for POST /intercept, with fail-open/closed handling."""
import logging
import uuid
from typing import Any, Optional

import httpx

from aicontrol_sdk.config import Config
from aicontrol_sdk.exceptions import (
    AIControlUnavailableError, PolicyDeniedError, ReviewPendingError, UnknownDecisionError,
)

logger = logging.getLogger("aicontrol_sdk.intercept_client")


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
        workflow: str = "unassigned",
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
            "workflow": workflow,
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
            response.raise_for_status()
        except httpx.HTTPError as exc:
            if self._config.fail_mode == "allow":
                return {"decision": "allow", "reason": "aicontrol_unavailable_fail_open"}
            raise AIControlUnavailableError(cause=exc) from exc

        result = response.json()

        decision = result["decision"]
        if decision == "allow":
            return result
        if decision == "deny":
            raise PolicyDeniedError(reason=result["reason"], policy_name=result.get("policy_name"))
        if decision == "review":
            raise ReviewPendingError(review_id=result["review_id"])
        raise UnknownDecisionError(decision=decision)

    def report_coverage(
        self, *, framework: str, hook: str, sdk_version: str,
        workflow: str, agent_name: Optional[str], silent_noop_warnings: list[str],
    ) -> None:
        """Fire-and-forget install-time handshake. Synchronous because patch()
        is: adapters bind at import time, where there is no running loop to
        schedule onto. Never raises -- a governance library must not take the
        host application down because the control plane was briefly
        unreachable at import time."""
        try:
            httpx.post(
                f"{self._config.url}/agents/{self._config.agent_id}/coverage",
                headers={"Authorization": f"Bearer {self._config.token}"},
                json={
                    "framework": framework,
                    "hook": hook,
                    "sdk_version": sdk_version,
                    "workflow": workflow,
                    "agent_name": agent_name,
                    "silent_noop_warnings": silent_noop_warnings,
                },
                timeout=2.0,
            )
        except Exception:
            # Deliberately broad: any failure here is a reporting failure, and
            # reporting must never be able to break the application it reports on.
            logger.warning("coverage_handshake_failed framework=%s", framework)

    async def report_response(
        self, tool_name: str, tool_response: Any, session_id: str, sequence_number: int,
    ) -> dict:
        """POST /intercept/report-response -- reports a tool's actual output
        back after it executes, for response scanning
        (agent_os.mcp_response_scanner via app/services/response_scanner.py).
        Advisory: never raises on a scan error or connection failure, since
        the tool has already executed by the time this is called -- there
        is nothing left to block by raising here (unlike intercept(), which
        runs before the tool executes and can legitimately abort it)."""
        body: dict[str, Any] = {
            "session_id": session_id,
            "agent_id": self._config.agent_id,
            "agent_name": self._config.agent_name,
            "tool_name": tool_name,
            "tool_response": tool_response,
            "sequence_number": sequence_number,
        }
        try:
            response = await self._client.post(
                "/intercept/report-response",
                headers={"Authorization": f"Bearer {self._config.token}"},
                json=body,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return {"decision": "allow", "reason": "report_response_unavailable"}

    async def aclose(self) -> None:
        await self._client.aclose()
