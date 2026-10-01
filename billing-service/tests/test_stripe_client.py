from unittest.mock import patch

import pytest

from app.services import stripe_client


def test_api_version_is_pinned():
    """stripe_client must set stripe.api_version explicitly, not rely on the
    SDK's own default -- otherwise upgrading the stripe package can silently
    change the API version the app talks to."""
    import importlib

    stripe_client.stripe.api_version = None
    try:
        importlib.reload(stripe_client)
        assert stripe_client.stripe.api_version == "2026-08-26.dahlia"
    finally:
        importlib.reload(stripe_client)


def test_create_checkout_session_business_plan():
    with patch("app.services.stripe_client.stripe.checkout.Session.create") as mock_create:
        mock_create.return_value = type("Obj", (), {"url": "https://checkout.stripe.com/session_123"})()

        url = stripe_client.create_checkout_session(plan="business", email="customer@example.com")

        assert url == "https://checkout.stripe.com/session_123"
        _, kwargs = mock_create.call_args
        assert kwargs["customer_email"] == "customer@example.com"
        assert kwargs["mode"] == "subscription"
        assert kwargs["line_items"] == [
            {"price": stripe_client.settings.stripe_price_id_business, "quantity": 1}
        ]
        assert kwargs["success_url"] == "https://aictl.io/pricing?checkout=success"
        assert kwargs["cancel_url"] == "https://aictl.io/pricing?checkout=cancel"
        assert kwargs["metadata"] == {"plan": "business"}


def test_create_checkout_session_enterprise_plan():
    with patch("app.services.stripe_client.stripe.checkout.Session.create") as mock_create:
        mock_create.return_value = type("Obj", (), {"url": "https://checkout.stripe.com/session_456"})()

        stripe_client.create_checkout_session(plan="enterprise", email="customer@example.com")

        _, kwargs = mock_create.call_args
        assert kwargs["line_items"] == [
            {"price": stripe_client.settings.stripe_price_id_enterprise, "quantity": 1}
        ]
        assert kwargs["metadata"] == {"plan": "enterprise"}


def test_create_checkout_session_without_email_omits_customer_email():
    with patch("app.services.stripe_client.stripe.checkout.Session.create") as mock_create:
        mock_create.return_value = type("Obj", (), {"url": "https://checkout.stripe.com/session_noemail"})()

        url = stripe_client.create_checkout_session(plan="business")

        assert url == "https://checkout.stripe.com/session_noemail"
        _, kwargs = mock_create.call_args
        assert "customer_email" not in kwargs
        assert "customer" not in kwargs
        assert kwargs["mode"] == "subscription"
        assert kwargs["metadata"] == {"plan": "business"}


def test_create_checkout_session_invalid_plan_raises():
    with pytest.raises(ValueError):
        stripe_client.create_checkout_session(plan="not-a-plan", email="customer@example.com")


def test_create_checkout_session_trial_plan_uses_payment_mode():
    with patch("app.services.stripe_client.stripe.checkout.Session.create") as mock_create:
        mock_create.return_value = type("Obj", (), {"url": "https://checkout.stripe.com/session_trial"})()

        url = stripe_client.create_checkout_session(plan="trial", email="customer@example.com")

        assert url == "https://checkout.stripe.com/session_trial"
        _, kwargs = mock_create.call_args
        assert kwargs["mode"] == "payment"
        assert kwargs["line_items"] == [
            {"price": stripe_client.settings.stripe_price_id_trial, "quantity": 1}
        ]
        assert kwargs["customer_email"] == "customer@example.com"
        assert kwargs["metadata"] == {"plan": "trial"}
        assert kwargs["success_url"] == "https://aictl.io/pricing?checkout=success"
        assert kwargs["cancel_url"] == "https://aictl.io/pricing?checkout=cancel"


def test_create_checkout_session_business_plan_still_subscription_mode():
    with patch("app.services.stripe_client.stripe.checkout.Session.create") as mock_create:
        mock_create.return_value = type("Obj", (), {"url": "https://checkout.stripe.com/session_business"})()

        stripe_client.create_checkout_session(plan="business", email="customer@example.com")

        _, kwargs = mock_create.call_args
        assert kwargs["mode"] == "subscription"


def test_create_checkout_session_with_existing_customer_id_passes_customer_not_email():
    with patch("app.services.stripe_client.stripe.checkout.Session.create") as mock_create:
        mock_create.return_value = type("Obj", (), {"url": "https://checkout.stripe.com/session_upgrade"})()

        stripe_client.create_checkout_session(
            plan="business", email="customer@example.com", existing_customer_id="cus_existing123"
        )

        _, kwargs = mock_create.call_args
        assert kwargs["customer"] == "cus_existing123"
        assert "customer_email" not in kwargs


def test_create_checkout_session_without_existing_customer_id_passes_email_not_customer():
    with patch("app.services.stripe_client.stripe.checkout.Session.create") as mock_create:
        mock_create.return_value = type("Obj", (), {"url": "https://checkout.stripe.com/session_new"})()

        stripe_client.create_checkout_session(plan="business", email="customer@example.com")

        _, kwargs = mock_create.call_args
        assert kwargs["customer_email"] == "customer@example.com"
        assert "customer" not in kwargs


def test_create_portal_session():
    with patch("app.services.stripe_client.stripe.billing_portal.Session.create") as mock_create:
        mock_create.return_value = type("Obj", (), {"url": "https://billing.stripe.com/session_789"})()

        url = stripe_client.create_portal_session(stripe_customer_id="cus_123")

        assert url == "https://billing.stripe.com/session_789"
        _, kwargs = mock_create.call_args
        assert kwargs["customer"] == "cus_123"
        assert kwargs["return_url"] == stripe_client.settings.stripe_portal_return_url
