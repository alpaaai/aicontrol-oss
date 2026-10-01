"""Tests for Slack actions endpoint."""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.core.config import settings


def _all_paths(routes):
    """Flatten app.routes, descending into FastAPI's _IncludedRouter wrappers."""
    paths = []
    for r in routes:
        if hasattr(r, "path"):
            paths.append(r.path)
        elif hasattr(r, "original_router"):
            paths.extend(_all_paths(r.original_router.routes))
    return paths


@pytest.mark.asyncio
async def test_slack_actions_route_exists():
    """POST /slack/actions route must be registered."""
    from app.main import app
    routes = _all_paths(app.routes)
    assert "/slack/actions" in routes


@pytest.mark.asyncio
async def test_slack_actions_rejects_bad_signature():
    """POST /slack/actions with invalid signature must return 403."""
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/slack/actions",
            content="payload={}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_handle_approve_updates_review():
    """handle_action must update hitl_review status to approved, and set
    reviewed_at (audit task 5.2 -- Slack path previously left it null unlike
    the API PATCH /reviews path)."""
    from app.routers.slack_actions import handle_action

    mock_session = AsyncMock()
    mock_review = MagicMock()
    mock_review.status = "pending"
    mock_review.reviewed_at = None
    mock_session.get = AsyncMock(return_value=mock_review)
    mock_session.flush = AsyncMock()

    with patch.object(settings, "slack_bot_token", ""):
        with patch("app.routers.slack_actions.WebClient"):
            await handle_action(
                session=mock_session,
                action_id="hitl_approve",
                review_id=uuid.uuid4(),
                reviewer="U123456",
            )

    assert mock_review.status == "approved"
    assert mock_review.reviewer == "U123456"
    assert mock_review.reviewed_at is not None


@pytest.mark.asyncio
async def test_handle_action_resolves_reviewer_email_via_slack_users_info():
    """When a bot token is configured, handle_action must resolve the raw
    Slack user ID to an email via users.info -- matching the identity format
    the API path stores (audit task 5.3)."""
    from app.routers.slack_actions import handle_action

    mock_session = AsyncMock()
    mock_review = MagicMock()
    mock_review.status = "pending"
    mock_session.get = AsyncMock(return_value=mock_review)
    mock_session.flush = AsyncMock()

    mock_client = MagicMock()
    mock_client.users_info.return_value = {
        "user": {"profile": {"email": "reviewer@aicontrol.dev"}}
    }

    with patch.object(settings, "slack_bot_token", "xoxb-real-token"):
        with patch("app.routers.slack_actions.WebClient", return_value=mock_client):
            await handle_action(
                session=mock_session,
                action_id="hitl_deny",
                review_id=uuid.uuid4(),
                reviewer="U123456",
            )

    mock_client.users_info.assert_called_once_with(user="U123456")
    assert mock_review.reviewer == "reviewer@aicontrol.dev"
    assert mock_review.status == "denied"


@pytest.mark.asyncio
async def test_handle_action_falls_back_to_slack_id_when_lookup_fails():
    """If users.info fails (missing scope, revoked token, etc.) handle_action
    must fall back to the raw Slack user ID rather than raising or losing the
    reviewer's identity entirely."""
    from app.routers.slack_actions import handle_action

    mock_session = AsyncMock()
    mock_review = MagicMock()
    mock_review.status = "pending"
    mock_session.get = AsyncMock(return_value=mock_review)
    mock_session.flush = AsyncMock()

    mock_client = MagicMock()
    mock_client.users_info.side_effect = Exception("missing_scope")

    with patch.object(settings, "slack_bot_token", "xoxb-real-token"):
        with patch("app.routers.slack_actions.WebClient", return_value=mock_client):
            await handle_action(
                session=mock_session,
                action_id="hitl_approve",
                review_id=uuid.uuid4(),
                reviewer="U123456",
            )

    assert mock_review.reviewer == "U123456"
