import pytest


def test_config_reads_from_env(monkeypatch):
    monkeypatch.setenv("AICONTROL_URL", "http://localhost:8001")
    monkeypatch.setenv("AICONTROL_TOKEN", "test-token")
    monkeypatch.setenv("AICONTROL_AGENT_ID", "agent-123")
    monkeypatch.setenv("AICONTROL_FAIL_MODE", "deny")

    from aicontrol_sdk.config import Config
    cfg = Config.from_env()

    assert cfg.url == "http://localhost:8001"
    assert cfg.token == "test-token"
    assert cfg.agent_id == "agent-123"
    assert cfg.fail_mode == "deny"


def test_config_fail_mode_defaults_to_deny(monkeypatch):
    monkeypatch.setenv("AICONTROL_URL", "http://localhost:8001")
    monkeypatch.setenv("AICONTROL_TOKEN", "test-token")
    monkeypatch.delenv("AICONTROL_FAIL_MODE", raising=False)
    monkeypatch.delenv("AICONTROL_AGENT_ID", raising=False)

    from aicontrol_sdk.config import Config
    cfg = Config.from_env()

    assert cfg.fail_mode == "deny"
    assert cfg.agent_id is None


def test_config_missing_url_raises():
    import os
    saved = os.environ.pop("AICONTROL_URL", None)
    try:
        from aicontrol_sdk.config import Config
        with pytest.raises(ValueError, match="AICONTROL_URL"):
            Config.from_env()
    finally:
        if saved is not None:
            os.environ["AICONTROL_URL"] = saved


def test_config_invalid_fail_mode_raises(monkeypatch):
    monkeypatch.setenv("AICONTROL_URL", "http://localhost:8001")
    monkeypatch.setenv("AICONTROL_TOKEN", "test-token")
    monkeypatch.setenv("AICONTROL_FAIL_MODE", "bogus")

    from aicontrol_sdk.config import Config
    with pytest.raises(ValueError, match="AICONTROL_FAIL_MODE"):
        Config.from_env()


def test_config_repr_does_not_leak_token():
    """repr(config) must not include the raw bearer token -- it can end up in
    logs, print() calls, or exception tracebacks that capture local variables."""
    from aicontrol_sdk.config import Config
    config = Config(url="http://x", token="SUPER-SECRET-TOKEN", agent_id="a")
    assert "SUPER-SECRET-TOKEN" not in repr(config)
