"""Tests for budget-threshold Slack alerting (WS3)."""
from unittest.mock import MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_alerts_when_over_80_percent_of_token_budget():
    from app.services.budget_alert_service import maybe_alert_budget_threshold

    policies = [{
        "rule_type": "tool_denylist", "name": "test_budget_alert_policy",
        "condition": {
            "blocked_tools": ["alert_probe_tool"],
            "token_budget": {"max_tokens": 100000, "window": "session", "on_exceed": "deny"},
        },
    }]

    with patch("app.services.budget_alert_service.WebClient") as mock_client_cls, \
         patch("app.services.budget_alert_service.get_license_info") as mock_license:
        mock_license.return_value.is_business = True
        with patch("app.services.budget_alert_service.settings") as mock_settings:
            mock_settings.slack_bot_token = "xoxb-real-token"
            mock_settings.slack_review_channel = "#aicontrol-reviews"
            await maybe_alert_budget_threshold(
                cumulative_tokens={"alert_probe_tool": 85000},
                cumulative_cost_usd={},
                active_policies=policies,
                tool_name="alert_probe_tool",
            )
        mock_client_cls.return_value.chat_postMessage.assert_called_once()


@pytest.mark.asyncio
async def test_does_not_alert_under_80_percent():
    from app.services.budget_alert_service import maybe_alert_budget_threshold

    policies = [{
        "rule_type": "tool_denylist", "name": "test_budget_alert_policy_2",
        "condition": {
            "blocked_tools": ["alert_probe_tool_2"],
            "token_budget": {"max_tokens": 100000, "window": "session", "on_exceed": "deny"},
        },
    }]

    with patch("app.services.budget_alert_service.WebClient") as mock_client_cls:
        await maybe_alert_budget_threshold(
            cumulative_tokens={"alert_probe_tool_2": 50000},
            cumulative_cost_usd={},
            active_policies=policies,
            tool_name="alert_probe_tool_2",
        )
        mock_client_cls.return_value.chat_postMessage.assert_not_called()


@pytest.mark.asyncio
async def test_skips_silently_when_not_business_tier():
    from app.services.budget_alert_service import maybe_alert_budget_threshold

    policies = [{
        "rule_type": "tool_denylist", "name": "test_budget_alert_policy_3",
        "condition": {
            "blocked_tools": ["alert_probe_tool_3"],
            "token_budget": {"max_tokens": 100000, "window": "session", "on_exceed": "deny"},
        },
    }]

    with patch("app.services.budget_alert_service.get_license_info") as mock_license, \
         patch("app.services.budget_alert_service.WebClient") as mock_client_cls:
        mock_license.return_value.is_business = False
        await maybe_alert_budget_threshold(
            cumulative_tokens={"alert_probe_tool_3": 99000},
            cumulative_cost_usd={},
            active_policies=policies,
            tool_name="alert_probe_tool_3",
        )
        mock_client_cls.return_value.chat_postMessage.assert_not_called()
