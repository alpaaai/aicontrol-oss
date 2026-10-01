"""Tests for settings loading from environment."""
import os
import pytest
from unittest.mock import patch


def test_settings_loads_database_url():
    """Settings must expose DATABASE_URL from environment."""
    env = {
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/db",
        "OPA_URL": "http://localhost:8181",
        "APP_ENV": "test",
        "SECRET_KEY": "test_secret",
    }
    with patch.dict(os.environ, env, clear=False):
        import importlib
        import app.core.config as cfg_module
        importlib.reload(cfg_module)
        from app.core.config import settings
        assert settings.database_url == "postgresql+asyncpg://u:p@localhost:5432/db"


def test_drift_unseen_tool_lookback_days_default():
    from app.core.config import Settings
    s = Settings(database_url="postgresql+asyncpg://x/y")
    assert s.drift_unseen_tool_lookback_days == 30


def test_production_rejects_default_secret_key():
    """A production deployment must never sign JWTs with the changeme default."""
    from app.core.config import Settings
    with pytest.raises(ValueError):
        Settings(database_url="postgresql+asyncpg://x/y", app_env="production")


def test_production_rejects_unset_secret_key():
    from app.core.config import Settings
    with pytest.raises(ValueError):
        Settings(
            database_url="postgresql+asyncpg://x/y",
            app_env="production",
            secret_key="",
        )


def test_production_accepts_real_secret_key():
    from app.core.config import Settings
    s = Settings(
        database_url="postgresql+asyncpg://x/y",
        app_env="production",
        secret_key="a-real-secret-value",
    )
    assert s.secret_key == "a-real-secret-value"


def test_development_allows_default_secret_key():
    """Dev/test envs must keep working without requiring a secret key."""
    from app.core.config import Settings
    s = Settings(database_url="postgresql+asyncpg://x/y", secret_key="changeme")
    assert s.secret_key == "changeme"


def test_demo_mode_defaults_to_disabled():
    """A real customer deployment must not expose the unauthenticated
    demo endpoints (they hard-delete audit_events/hitl_reviews) unless
    explicitly opted in. tests/conftest.py sets DEMO_MODE=true in the test
    process env so the demo router test suite works -- clear it here to
    check the actual class default, not the test env override."""
    from app.core.config import Settings
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("DEMO_MODE", None)
        s = Settings(database_url="postgresql+asyncpg://x/y")
    assert s.DEMO_MODE is False


def test_demo_mode_can_be_explicitly_enabled():
    from app.core.config import Settings
    s = Settings(database_url="postgresql+asyncpg://x/y", DEMO_MODE=True)
    assert s.DEMO_MODE is True

