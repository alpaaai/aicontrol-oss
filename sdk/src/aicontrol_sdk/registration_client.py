"""Calls POST /agents/register for zero-friction agent self-registration."""
from typing import Optional

import httpx

from aicontrol_sdk.config import Config


class RegistrationClient:
    def __init__(self, config: Config, transport: Optional[httpx.BaseTransport] = None):
        self._config = config
        self._client = httpx.AsyncClient(base_url=config.url, transport=transport, timeout=5.0)
        self._cache: dict[str, str] = {}

    async def register_agent(
        self,
        name: str,
        owner: str = "sdk-auto-registered",
        framework: Optional[str] = None,
    ) -> str:
        """Idempotent get-or-create by name. Caches per-process to avoid re-registering
        on every instrument() call within the same run."""
        if name in self._cache:
            return self._cache[name]

        response = await self._client.post(
            "/agents/register",
            headers={"Authorization": f"Bearer {self._config.token}"},
            json={"name": name, "owner": owner, "framework": framework},
        )
        response.raise_for_status()
        agent_id = response.json()["id"]
        self._cache[name] = agent_id
        return agent_id

    async def aclose(self) -> None:
        await self._client.aclose()
