import os
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    """Walk up from this file's location to find the nearest .env file."""
    search = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = search / ".env"
        if candidate.is_file():
            return str(candidate)
        search = search.parent
    return ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str
    WAL_DIR: str = "./data/wal"
    REPORTS_DIR: str = "./data/reports"
    MCP_RESPONSE_SCAN_POLICY: Literal["block", "log"] = "block"
    drift_scan_interval_hours: int = 6
    drift_unseen_tool_lookback_days: int = 30
    retention_purge_interval_hours: int = 24
    REVIEW_TIMEOUT_MINUTES: int = 60
    HITL_RETRY_WINDOW_MINUTES: int = 15
    app_env: str = "development"
    secret_key: str = "changeme"
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_review_channel: str = "#aicontrol-reviews"
    CORS_ORIGINS: str = "http://localhost:3000"
    FRONTEND_BASE_URL: str = "http://localhost:3000"
    # billing-service base URL. Operator-level deployment fact (not
    # per-org state, unlike OrgSettings.activation_code) -- used by
    # app/services/billing_client.py.
    AICONTROL_LICENSE_SYNC_URL: str = "https://billing.aictl.io"

    # Demo dashboard — pre-issued agent JWT for browser-based demo runner.
    DEMO_TOKEN: str = ""
    # Gates app/routers/demo.py (unauthenticated seed/reset/call_tool endpoints
    # that hard-delete rows from audit_events/hitl_reviews). Off by default:
    # a real customer deployment must opt in explicitly. AIControl's own
    # sales-demo environment sets this to true.
    DEMO_MODE: bool = False

    # AI-native features — customer's own LLM account. AIControl never bills tokens.
    LLM_PROVIDER: str = "anthropic"
    LLM_MODEL: str = "claude-haiku-4-5-20251001"
    LLM_API_KEY: str = ""
    LLM_MOCK_ENABLED: bool = False
    LLM_MAX_LATENCY_MS: int = 3000

    @model_validator(mode="after")
    def _require_real_secret_key_in_production(self) -> "Settings":
        if self.app_env == "production" and (not self.secret_key or self.secret_key == "changeme"):
            raise ValueError(
                "SECRET_KEY must be set to a real, non-default value when APP_ENV=production. "
                "Signing JWTs with the 'changeme' default lets anyone forge an admin token."
            )
        return self


settings = Settings()
