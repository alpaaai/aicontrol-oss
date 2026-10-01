from unittest.mock import patch

import stripe
from fastapi.testclient import TestClient

from app.core.rate_limiter import reset_rate_limits
from app.main import app

client = TestClient(app)


def _reset():
    reset_rate_limits()


def test_checkout_happy_path():
    _reset()
    with patch("app.routers.billing.stripe_client.create_checkout_session") as mock_create:
        mock_create.return_value = "https://checkout.stripe.com/session_123"

        response = client.post(
            "/billing/checkout", json={"plan": "business", "email": "customer@example.com"}
        )

        assert response.status_code == 200
        assert response.json() == {"url": "https://checkout.stripe.com/session_123"}
        mock_create.assert_called_once_with(plan="business", email="customer@example.com")


def test_checkout_trial_plan_accepted():
    _reset()
    with patch("app.routers.billing.stripe_client.create_checkout_session") as mock_create:
        mock_create.return_value = "https://checkout.stripe.com/session_trial"

        response = client.post(
            "/billing/checkout", json={"plan": "trial", "email": "customer@example.com"}
        )

        assert response.status_code == 200
        assert response.json() == {"url": "https://checkout.stripe.com/session_trial"}
        mock_create.assert_called_once_with(plan="trial", email="customer@example.com")


def test_checkout_without_email_accepted():
    _reset()
    with patch("app.routers.billing.stripe_client.create_checkout_session") as mock_create:
        mock_create.return_value = "https://checkout.stripe.com/session_noemail"

        response = client.post("/billing/checkout", json={"plan": "business"})

        assert response.status_code == 200
        assert response.json() == {"url": "https://checkout.stripe.com/session_noemail"}
        mock_create.assert_called_once_with(plan="business", email=None)


def test_checkout_invalid_plan_returns_400():
    _reset()
    with patch("app.routers.billing.stripe_client.create_checkout_session") as mock_create:
        mock_create.side_effect = ValueError("unknown plan: not-a-plan")

        response = client.post(
            "/billing/checkout", json={"plan": "not-a-plan", "email": "customer@example.com"}
        )

        assert response.status_code == 400


def test_checkout_stripe_api_error_returns_clean_502():
    _reset()
    with patch("app.routers.billing.stripe_client.create_checkout_session") as mock_create:
        mock_create.side_effect = stripe.error.APIConnectionError("could not connect to Stripe")

        response = client.post(
            "/billing/checkout", json={"plan": "business", "email": "customer@example.com"}
        )

        assert response.status_code == 502
        assert response.json() == {"detail": "payment provider error, please try again"}


def test_checkout_rate_limited_after_five_attempts():
    _reset()
    with patch("app.routers.billing.stripe_client.create_checkout_session") as mock_create:
        mock_create.return_value = "https://checkout.stripe.com/session_123"

        for _ in range(5):
            response = client.post(
                "/billing/checkout", json={"plan": "business", "email": "customer@example.com"}
            )
            assert response.status_code == 200

        response = client.post(
            "/billing/checkout", json={"plan": "business", "email": "customer@example.com"}
        )
        assert response.status_code == 429
