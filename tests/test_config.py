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

