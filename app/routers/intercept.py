"""POST /intercept — core tool call intercept endpoint."""
import time
import uuid
from typing import Any, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_agent
from app.core.logging import get_logger
from app.models.database import get_db
from app.models.schemas import Agent
from app.services.audit_writer import write_event
from app.services.budget_alert_service import maybe_alert_budget_threshold
from app.services.governance_engine import evaluate_tool_call
from app.services.hitl_service import create_hitl_review, post_slack_review
from app.services.response_scanner import scan_tool_response
from app.services.session_tracking import RISK_SCORE_DELTA, accumulate_session_risk, ensure_session
from app.services.wal import default_wal_writer as wal_writer

router = APIRouter()
logger = get_logger("intercept")


class InterceptRequest(BaseModel):
    session_id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str
    tool_name: str
    tool_parameters: dict[str, Any] = {}
    sequence_number: int
    # Defaulted rather than nullable on the wire, so the grouping dimension
    # always has a value even from an adapter that cannot resolve one.
    workflow: str = "unassigned"
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None


class InterceptResponse(BaseModel):
    decision: str
    reason: str
    audit_event_id: uuid.UUID
    review_id: Optional[uuid.UUID] = None
    policy_id: Optional[str] = None
    policy_name: Optional[str] = None


def enrich_parameters(tool_name: str, tool_parameters: dict[str, Any]) -> dict[str, Any]:
    """Enrich tool_parameters before persisting. Extracts domain from HTTP tool URLs."""
    params = dict(tool_parameters)
    if tool_name in ("http_get", "http_post", "http_put", "http_delete", "http_patch"):
        url = params.get("url", "")
        if url:
            parsed = urlparse(url)
            if parsed.netloc:
                params["domain"] = parsed.netloc
    return params


@router.post("/intercept", response_model=InterceptResponse)
async def intercept(
    body: InterceptRequest,
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(require_agent),
) -> InterceptResponse:
    """
    Intercept a tool call, evaluate against policies, write audit event.
    Returns allow | deny | review plus the audit event ID.
    """
    # Enforce agent-scoped token binding: agent tokens may only intercept for their own agent_id
    if token.get("role") == "agent" and token.get("agent_id") is not None:
        if str(token["agent_id"]) != str(body.agent_id):
            raise HTTPException(
                status_code=403,
                detail="Token is scoped to a different agent",
            )

    start = time.monotonic()

    # Step 2b: approved_tools enforcement gate — runs before the engine, but must
    # still respect observe mode (never blocks, only records).
    # Case-sensitive match: tool_name is never normalized upstream.
    # approved_tools = [] means unrestricted (backward compatible).
    # Agent not found in DB also means unrestricted (backward compatible).
    agent_result = await db.execute(select(Agent).where(Agent.id == body.agent_id))
    agent = agent_result.scalar_one_or_none()
    is_observe_mode = agent is not None and agent.governance_mode == "observe"
    if agent is not None and agent.approved_tools:
        if body.tool_name not in agent.approved_tools:
            early_duration_ms = int((time.monotonic() - start) * 1000)
            enriched_early = enrich_parameters(body.tool_name, body.tool_parameters)
            await ensure_session(db, body.session_id, body.agent_id)
            early_event_id = wal_writer.append({
                "session_id": str(body.session_id),
                "agent_id": str(body.agent_id),
                "agent_name": body.agent_name,
                "tool_name": body.tool_name,
                "tool_parameters": enriched_early,
                "decision": "deny",
                "decision_reason": "tool_not_approved_for_agent",
                "workflow": body.workflow,
                "sequence_number": body.sequence_number,
                "duration_ms": early_duration_ms,
                "risk_delta": RISK_SCORE_DELTA["deny"],
                "policy_name": "approved_tools",
                "policy_id": None,
                "bypass": False,
                "enforced": not is_observe_mode,
            })
            return InterceptResponse(
                decision="allow" if is_observe_mode else "deny",
                reason="tool_not_approved_for_agent",
                audit_event_id=early_event_id,
                review_id=None,
            )

    gov_result = await evaluate_tool_call(
        db,
        agent=agent,
        agent_name=body.agent_name,
        tool_name=body.tool_name,
        tool_parameters=body.tool_parameters,
        workflow=body.workflow,
        session_id=body.session_id,
    )
    import asyncio
    asyncio.create_task(maybe_alert_budget_threshold(
        cumulative_tokens=gov_result.cumulative_tokens,
        cumulative_cost_usd=gov_result.cumulative_cost_usd,
        active_policies=gov_result.policies,
        tool_name=body.tool_name,
    ))

    duration_ms = int((time.monotonic() - start) * 1000)

    # Enrich parameters (e.g. extract domain from HTTP tool URLs)
    enriched_parameters = enrich_parameters(body.tool_name, body.tool_parameters)

    # Cedar names the policy that fired directly — no reverse-engineering needed
    fired_policy_id: Optional[str] = gov_result.fired_policy_id
    fired_policy_name: Optional[str] = gov_result.fired_policy_name

    # Ensure session row exists (auto-create if agent didn't pre-register)
    await ensure_session(db, body.session_id, body.agent_id)

    true_decision = gov_result.decision
    true_reason = gov_result.reason
    enforced_decision = "allow" if is_observe_mode else true_decision

    if gov_result.bypass:
        logger.critical(
            "engine_bypass_event",
            tool_name=body.tool_name,
            agent_id=str(body.agent_id),
            decision=true_decision,
            reason=true_reason,
        )

    review_id: Optional[uuid.UUID] = None
    # The "review" path creates a HITLReview row with a real FK to
    # audit_events.id — that row must already exist in Postgres, so this
    # path writes synchronously rather than through the async WAL. allow/deny
    # (the hot-path majority) write through the WAL instead.
    if true_decision == "review" and not is_observe_mode:
        event_id = await write_event(
            session=db,
            session_id=body.session_id,
            agent_id=body.agent_id,
            agent_name=body.agent_name,
            tool_name=body.tool_name,
            tool_parameters=enriched_parameters,
            decision=true_decision,
            decision_reason=true_reason,
            workflow=body.workflow,
            sequence_number=body.sequence_number,
            duration_ms=duration_ms,
            risk_delta=RISK_SCORE_DELTA.get(true_decision, 0),
            policy_name=fired_policy_name,
            policy_id=uuid.UUID(fired_policy_id) if fired_policy_id else None,
            input_tokens=body.input_tokens,
            output_tokens=body.output_tokens,
            cost_usd=body.cost_usd,
        )
        review_id = await create_hitl_review(
            session=db,
            audit_event_id=event_id,
            session_id=body.session_id,
        )
        await accumulate_session_risk(db, body.session_id, RISK_SCORE_DELTA.get(true_decision, 0))
        import asyncio
        asyncio.create_task(
            post_slack_review(
                review_id=review_id,
                audit_event_id=event_id,
                agent_name=body.agent_name,
                tool_name=body.tool_name,
                tool_parameters=body.tool_parameters,
                decision_reason=true_reason,
            )
        )
    else:
        event_id = wal_writer.append({
            "session_id": str(body.session_id),
            "agent_id": str(body.agent_id),
            "agent_name": body.agent_name,
            "tool_name": body.tool_name,
            "tool_parameters": enriched_parameters,
            "tool_response": None,
            "policy_id": fired_policy_id or None,
            "policy_name": fired_policy_name or None,
            "decision": true_decision,
            "decision_reason": true_reason,
            "workflow": body.workflow,
            "sequence_number": body.sequence_number,
            "duration_ms": duration_ms,
            "risk_delta": RISK_SCORE_DELTA.get(true_decision, 0),
            "input_tokens": body.input_tokens,
            "output_tokens": body.output_tokens,
            "cost_usd": body.cost_usd,
            "bypass": gov_result.bypass,
            "enforced": not is_observe_mode,
        })
        await accumulate_session_risk(db, body.session_id, RISK_SCORE_DELTA.get(true_decision, 0))

    logger.info(
        "tool_intercepted",
        tool_name=body.tool_name,
        decision=enforced_decision,
        agent_name=body.agent_name,
        duration_ms=duration_ms,
        session_id=str(body.session_id),
    )

    return InterceptResponse(
        decision=enforced_decision,
        reason=true_reason,
        audit_event_id=event_id,
        review_id=review_id,
        policy_id=fired_policy_id,
        policy_name=fired_policy_name,
    )


class ReportResponseRequest(BaseModel):
    session_id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str
    tool_name: str
    tool_response: Any = None
    sequence_number: int


class ReportResponseResponse(BaseModel):
    decision: str
    reason: str
    audit_event_id: uuid.UUID


@router.post("/intercept/report-response", response_model=ReportResponseResponse)
async def report_response(
    body: ReportResponseRequest,
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(require_agent),
) -> ReportResponseResponse:
    """Post-tool-call round-trip: the SDK calls this after the real tool
    executes, reporting its output back for scanning. /intercept itself
    only ever ran pre-tool-call -- this is the first time the direct SDK
    path sees a tool's actual response."""
    from app.core.config import settings

    if token.get("role") == "agent" and token.get("agent_id") is not None:
        if str(token["agent_id"]) != str(body.agent_id):
            raise HTTPException(status_code=403, detail="Token is scoped to a different agent")

    scan_result = scan_tool_response(body.tool_response, body.tool_name)

    if not scan_result.is_safe:
        decision = "deny" if settings.MCP_RESPONSE_SCAN_POLICY == "block" else "allow"
        reason = f"response_scan_flagged:{','.join(t.category for t in scan_result.threats)}"
        logger.warning("intercept_response_scan_flagged", tool_name=body.tool_name, agent_name=body.agent_name)
    else:
        decision, reason = "allow", "response_scan_clean"

    await ensure_session(db, body.session_id, body.agent_id)
    event_id = wal_writer.append({
        "session_id": str(body.session_id), "agent_id": str(body.agent_id), "agent_name": body.agent_name,
        "tool_name": body.tool_name, "tool_parameters": {}, "tool_response": None,
        "decision": decision, "decision_reason": reason,
        "sequence_number": body.sequence_number, "duration_ms": 0,
        "risk_delta": RISK_SCORE_DELTA.get(decision, 0),
        "bypass": False, "enforced": True,
    })

    return ReportResponseResponse(decision=decision, reason=reason, audit_event_id=event_id)
