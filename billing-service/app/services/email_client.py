"""Transactional email via Resend's HTTP API. No SDK dependency."""
import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("email_client")

GETTING_STARTED_URL = "https://aictl.io/docs/getting-started"
_RESEND_URL = "https://api.resend.com/emails"


def send_activation_email(to: str, activation_code: str) -> None:
    """Email a newly generated activation code. Never raises -- a failed
    send is logged and swallowed so it can't roll back the billing_customers
    row the caller already committed for a paying customer."""
    try:
        response = httpx.post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.resend_from_address,
                "to": [to],
                "subject": "Your AIControl activation code",
                "html": (
                    f"<p>Your activation code is: <strong>{activation_code}</strong></p>"
                    f'<p>Get started: <a href="{GETTING_STARTED_URL}">{GETTING_STARTED_URL}</a></p>'
                ),
            },
            timeout=10.0,
        )
        response.raise_for_status()
    except Exception:
        logger.error("activation_email_send_failed", to=to)
