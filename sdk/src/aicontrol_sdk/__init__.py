"""AIControl SDK — instrument() auto-patch and @control decorator."""
import os
from dataclasses import dataclass
from typing import Optional

from aicontrol_sdk import adapters
from aicontrol_sdk.config import Config
from aicontrol_sdk.decorator import control
from aicontrol_sdk.exceptions import AIControlUnavailableError, PolicyDeniedError, ReviewPendingError
from aicontrol_sdk.intercept_client import InterceptClient
from aicontrol_sdk.registration_client import RegistrationClient

__all__ = [
    "instrument",
    "control",
    "PolicyDeniedError",
    "ReviewPendingError",
    "AIControlUnavailableError",
    "Instrumented",
]


@dataclass
class Instrumented:
    """Result of instrument() — the resolved agent_id and intercept client in use."""
    agent_id: str
    client: InterceptClient
    adapter: object


async def instrument(
    agent_name: str,
    url: Optional[str] = None,
    token: Optional[str] = None,
    framework: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> Instrumented:
    """Auto-register this agent (if agent_id not given) and patch the detected
    or explicitly named framework adapter to call AIControl before every tool call.

    url/token default to AICONTROL_URL/AICONTROL_TOKEN env vars when omitted.
    """
    config = Config(
        url=url or os.environ["AICONTROL_URL"],
        token=token or os.environ["AICONTROL_TOKEN"],
        agent_name=agent_name,
        fail_mode=os.environ.get("AICONTROL_FAIL_MODE", "deny"),  # type: ignore[arg-type]
    )

    if agent_id is None:
        registration_client = RegistrationClient(config=config)
        agent_id = await registration_client.register_agent(name=agent_name, framework=framework)

    config.agent_id = agent_id
    client = InterceptClient(config=config)

    adapter = adapters.get(framework) if framework else adapters.detect()
    adapter.patch(client)

    return Instrumented(agent_id=agent_id, client=client, adapter=adapter)
