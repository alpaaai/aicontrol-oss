from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str
    opa_url: str = "http://localhost:8181"
    opa_failure_mode: Literal["deny", "allow"] = "deny"
    opa_poll_interval_seconds: int = 30
    drift_scan_interval_hours: int = 6
    REVIEW_TIMEOUT_MINUTES: int = 60
    app_env: str = "development"
    secret_key: str = "changeme"
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_review_channel: str = "#aicontrol-reviews"
    AICONTROL_LICENSE_KEY: str = ""
    CORS_ORIGINS: str = "http://localhost:3000"
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # AI-native features — customer's own LLM account. AIControl never bills tokens.
    LLM_PROVIDER: str = "anthropic"
    LLM_MODEL: str = "claude-haiku-4-5-20251001"
    LLM_API_KEY: str = ""
    LLM_MOCK_ENABLED: bool = False
    LLM_MAX_LATENCY_MS: int = 3000


settings = Settings()
