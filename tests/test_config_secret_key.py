"""Startup warning for a short SECRET_KEY in production."""
from app.core.config import secret_key_warning


def test_short_production_secret_key_produces_a_warning():
    assert "32" in secret_key_warning("shortkey", "production")


def test_long_production_secret_key_is_fine():
    assert secret_key_warning("x" * 32, "production") is None


def test_short_key_outside_production_is_not_warned_about():
    assert secret_key_warning("dev", "development") is None
