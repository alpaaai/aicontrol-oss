import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_instrument_registers_agent_and_patches_detected_adapter():
    from aicontrol_sdk import instrument

    fake_adapter = MagicMock()
    fake_adapter.name = "fake"
    fake_adapter.is_available.return_value = True
    fake_adapter.patch = MagicMock()

    with patch("aicontrol_sdk.adapters.detect", return_value=fake_adapter), patch(
        "aicontrol_sdk.registration_client.RegistrationClient.register_agent",
        new=AsyncMock(return_value="agent-42"),
    ):
        result = await instrument(agent_name="my-agent", url="http://aicontrol.test", token="tok")

    assert result.agent_id == "agent-42"
    fake_adapter.patch.assert_called_once()


@pytest.mark.asyncio
async def test_instrument_uses_explicit_framework_when_given():
    from aicontrol_sdk import instrument
    from aicontrol_sdk.adapters import ADAPTER_REGISTRY

    fake_adapter = MagicMock()
    fake_adapter.name = "explicit-fake"
    fake_adapter.patch = MagicMock()
    ADAPTER_REGISTRY["explicit-fake"] = fake_adapter

    with patch(
        "aicontrol_sdk.registration_client.RegistrationClient.register_agent",
        new=AsyncMock(return_value="agent-42"),
    ):
        await instrument(
            agent_name="my-agent", url="http://aicontrol.test", token="tok",
            framework="explicit-fake",
        )

    fake_adapter.patch.assert_called_once()
    ADAPTER_REGISTRY.pop("explicit-fake", None)


@pytest.mark.asyncio
async def test_instrument_skips_registration_when_agent_id_given():
    from aicontrol_sdk import instrument

    fake_adapter = MagicMock()
    fake_adapter.name = "fake2"
    fake_adapter.is_available.return_value = True
    fake_adapter.patch = MagicMock()

    register_mock = AsyncMock(return_value="should-not-be-used")
    with patch("aicontrol_sdk.adapters.detect", return_value=fake_adapter), patch(
        "aicontrol_sdk.registration_client.RegistrationClient.register_agent", new=register_mock
    ):
        result = await instrument(
            agent_name="my-agent", url="http://aicontrol.test", token="tok",
            agent_id="already-known-id",
        )

    assert result.agent_id == "already-known-id"
    register_mock.assert_not_awaited()
