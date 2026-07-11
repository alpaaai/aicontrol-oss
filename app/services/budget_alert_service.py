"""Budget-threshold Slack alerting (WS3) — fires when cumulative token/cost
usage crosses 80% of a token_budget policy's max_tokens/max_cost_usd, so an
operator can react before the hard deny/review fires. Structurally mirrors
app/services/hitl_service.py's post_slack_review (license check, bot-token
check, WebClient usage) — this is a second, independent Slack message type,
not a review request.
"""
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from app.core.config import settings
from app.core.license_gate import get_license_info
from app.core.logging import get_logger

logger = get_logger("budget_alert_service")

ALERT_THRESHOLD_RATIO = 0.8


async def maybe_alert_budget_threshold(
    cumulative_tokens: dict[str, float],
    cumulative_cost_usd: dict[str, float],
    active_policies: list[dict[str, Any]],
    tool_name: str,
) -> None:
    """No-op unless a token_budget policy targeting tool_name has crossed
    80% of its threshold. Silently skips (logged) if Slack isn't configured
    or the license isn't Business+ — never raises, this is advisory only."""
    license_info = get_license_info()
    if not license_info.is_business:
        logger.info("budget_alert_skipped", reason="requires Business or Enterprise license")
        return

    for policy in active_policies:
        if policy.get("rule_type") != "tool_denylist":
            continue
        condition = policy.get("condition", {})
        token_budget = condition.get("token_budget")
        if not token_budget or tool_name not in condition.get("blocked_tools", []):
            continue

        if token_budget.get("max_tokens"):
            actual = cumulative_tokens.get(tool_name, 0)
            threshold = token_budget["max_tokens"] * ALERT_THRESHOLD_RATIO
            if actual >= threshold:
                await _post_alert(policy["name"], tool_name, "tokens", actual, token_budget["max_tokens"])
                return

        if token_budget.get("max_cost_usd"):
            actual = cumulative_cost_usd.get(tool_name, 0)
            threshold = token_budget["max_cost_usd"] * ALERT_THRESHOLD_RATIO
            if actual >= threshold:
                await _post_alert(policy["name"], tool_name, "cost_usd", actual, token_budget["max_cost_usd"])
                return


async def _post_alert(policy_name: str, tool_name: str, dimension: str, actual: float, max_value: float) -> None:
    if not settings.slack_bot_token or settings.slack_bot_token == "xoxb-placeholder":
        logger.warning("budget_alert_skipped", reason="SLACK_BOT_TOKEN not configured")
        return

    client = WebClient(token=settings.slack_bot_token)
    try:
        client.chat_postMessage(
            channel=settings.slack_review_channel,
            text=(
                f":warning: Budget threshold warning — `{tool_name}` is at "
                f"{actual:.0f}/{max_value:.0f} {dimension} ({actual / max_value:.0%}) "
                f"under policy `{policy_name}`."
            ),
        )
        logger.info("budget_alert_sent", tool_name=tool_name, dimension=dimension, actual=actual, max_value=max_value)
    except SlackApiError as e:
        logger.error("budget_alert_failed", error=str(e), tool_name=tool_name)
