"""POST /slack/actions — handles Slack interactive button callbacks."""
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime
from urllib.parse import unquote_plus
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slack_sdk import WebClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.database import get_db
from app.models.schemas import HITLReview

router = APIRouter()
logger = get_logger("slack_actions")


def _verify_slack_signature(request_body: bytes, headers: dict) -> bool:
    """Verify Slack request signature to prevent spoofing."""
    if not settings.slack_signing_secret or \
       settings.slack_signing_secret == "placeholder":
        return False

    timestamp = headers.get("x-slack-request-timestamp", "")
    slack_signature = headers.get("x-slack-signature", "")

    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except ValueError:
        return False

    sig_basestring = f"v0:{timestamp}:{request_body.decode()}"
    computed = "v0=" + hmac.new(
        settings.slack_signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, slack_signature)


def _resolve_reviewer_email(client: WebClient, slack_user_id: str) -> str:
    """Resolve a Slack user ID to their email via users.info, for audit-identity
    consistency with the API review path (which stores the human JWT's email
    claim). Falls back to the raw Slack user ID if the lookup fails or the
    workspace hasn't granted the users:read.email scope."""
    try:
        response = client.users_info(user=slack_user_id)
        email = response.get("user", {}).get("profile", {}).get("email")
        return email or slack_user_id
    except Exception as e:
        logger.warning(
            "slack_user_lookup_failed", slack_user_id=slack_user_id, error=str(e)
        )
        return slack_user_id


async def handle_action(
    session: AsyncSession,
    action_id: str,
    review_id: uuid.UUID,
    reviewer: str,
) -> None:
    """Update HITLReview row based on approve/deny action.

    `reviewer` is the raw Slack user ID from the interaction payload; it is
    resolved to an email address (matching the API review path's identity
    format) when a bot token is configured.
    """
    review = await session.get(HITLReview, review_id, with_for_update=True)
    if not review:
        logger.warning("hitl_review_not_found", review_id=str(review_id))
        return

    if review.status != "pending":
        logger.info("hitl_already_resolved", review_id=str(review_id),
                    status=review.status)
        return

    client = None
    if settings.slack_bot_token and \
       settings.slack_bot_token != "xoxb-placeholder":
        client = WebClient(token=settings.slack_bot_token)

    reviewer_identity = _resolve_reviewer_email(client, reviewer) if client else reviewer

    new_status = "approved" if action_id == "hitl_approve" else "denied"
    review.status = new_status
    review.reviewer = reviewer_identity
    review.reviewed_at = datetime.utcnow()
    await session.flush()

    logger.info(
        "hitl_resolved",
        review_id=str(review_id),
        status=new_status,
        reviewer=reviewer_identity,
    )

    if client:
        icon = "Approved" if new_status == "approved" else "Denied"
        try:
            client.chat_postMessage(
                channel=settings.slack_review_channel,
                text=f"{icon}: Review `{str(review_id)[:8]}...` by {reviewer_identity}",
            )
        except Exception as e:
            logger.error("slack_confirmation_failed", error=str(e))


@router.post("/slack/actions")
async def slack_actions(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Handle Slack interactive component callbacks."""
    body = await request.body()
    headers = dict(request.headers)

    if not _verify_slack_signature(body, headers):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Slack signature",
        )

    body_str = body.decode()
    payload_str = unquote_plus(body_str.replace("payload=", "", 1))
    payload = json.loads(payload_str)

    actions = payload.get("actions", [])
    if not actions:
        return {"ok": True}

    action = actions[0]
    action_id = action.get("action_id")
    review_id_str = action.get("value")
    reviewer = payload.get("user", {}).get("id", "unknown")

    if action_id not in ("hitl_approve", "hitl_deny"):
        logger.warning("unknown_action", action_id=action_id)
        return {"ok": True}

    try:
        review_id = uuid.UUID(review_id_str)
    except ValueError:
        logger.error("invalid_review_id", value=review_id_str)
        return {"ok": True}

    await handle_action(
        session=db,
        action_id=action_id,
        review_id=review_id,
        reviewer=reviewer,
    )

    return {"ok": True}
