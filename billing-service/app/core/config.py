from pathlib import Path

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

    database_url: str = "postgresql+asyncpg://billing:billing@localhost:5433/billing"
    app_env: str = "development"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_business: str = ""
    stripe_price_id_enterprise: str = ""
    stripe_price_id_trial: str = ""
    stripe_portal_return_url: str = "https://aictl.io/pricing"

    resend_api_key: str = ""
    resend_from_address: str = "AIControl <no-reply@aictl.io>"


settings = Settings()
