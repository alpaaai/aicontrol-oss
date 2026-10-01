from unittest.mock import patch

from app.core.config import settings
from app.services.email_client import GETTING_STARTED_URL, send_activation_email


def test_send_activation_email_calls_resend_with_correct_params():
    with patch("app.services.email_client.httpx.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None

        send_activation_email(to="customer@example.com", activation_code="abc123")

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.resend.com/emails"
        assert kwargs["headers"]["Authorization"] == f"Bearer {settings.resend_api_key}"
        body = kwargs["json"]
        assert body["from"] == settings.resend_from_address
        assert body["from"] == "AIControl <no-reply@aictl.io>"
        assert body["to"] == ["customer@example.com"]
        assert "abc123" in body["html"]
        assert GETTING_STARTED_URL in body["html"]


def test_send_activation_email_failure_is_logged_not_raised():
    with patch("app.services.email_client.httpx.post") as mock_post:
        mock_post.side_effect = Exception("resend is down")

        send_activation_email(to="customer@example.com", activation_code="abc123")
