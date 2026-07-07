import pytest
from aicontrol_sdk.config import Config


@pytest.fixture
def config():
    return Config(url="http://aicontrol.test", token="tok-123", agent_id="agent-1", fail_mode="deny")


@pytest.fixture
def config_fail_open():
    return Config(url="http://aicontrol.test", token="tok-123", agent_id="agent-1", fail_mode="allow")
