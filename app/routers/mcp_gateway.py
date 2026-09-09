"""In-process MCP gateway (Decision 12, plans/2026-09-07-gateway-pivot.md).
Agents point their MCP client at /mcp/{server_id}/... instead of self-reporting
to /intercept. Rebuilds the shape of the deleted enterprise/mcp_gateway/
against Cedar (via app.services.governance_engine) instead of OPA, and fixes
its three known gaps: unauthenticated ingress (Task 2's require_gateway_agent),
unvalidated agent_id claims (same fix — identity comes only from the token),
and fail-open on unreachable downstream (explicit JSON-RPC error, this task).
"""
import uuid
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_gateway_agent
from app.core.logging import get_logger
from app.models.database import get_db
from app.models.mcp_server import MCPServer
from app.models.schemas import Agent
from app.services.audit_writer import write_event
from app.services.governance_engine import evaluate_tool_call
from app.services.hitl_service import create_hitl_review, post_slack_review
from app.services.response_scanner import scan_tool_response
from app.services.session_tracking import RISK_SCORE_DELTA, accumulate_session_risk, ensure_session
from app.services.wal import default_wal_writer as wal_writer

router = APIRouter(prefix="/mcp", tags=["mcp_gateway"])
logger = get_logger("mcp_gateway")

UPSTREAM_UNREACHABLE = {
    "jsonrpc": "2.0", "id": None,
    "error": {"code": -32000, "message": "Downstream MCP server unreachable"},
}


async def _get_server(db: AsyncSession, server_id: uuid.UUID) -> MCPServer:
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not registered")
    if server.status != "active":
        raise HTTPException(status_code=403, detail=f"MCP server status is '{server.status}', not 'active'")
    return server


async def forward_to_upstream(server: MCPServer, method: str, body: dict, auth_header: Optional[str]) -> dict:
    """Forward a JSON-RPC request to the registered downstream server.
    Pure passthrough (Decision 9): auth_header is whatever the gateway
    caller's own Authorization header carried, forwarded unchanged. No
    credential is read from or written to the MCPServer row."""
    headers = {"Authorization": auth_header} if auth_header else {}
    async with httpx.AsyncClient() as client:
        response = await client.post(server.base_url, json=body, headers=headers, timeout=10.0)
        response.raise_for_status()
        return response.json()


@router.post("/{server_id}/tools/list")
async def tools_list(
    server_id: uuid.UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(require_gateway_agent),
    authorization: Optional[str] = Header(default=None),
) -> dict:
    server = await _get_server(db, server_id)
    try:
        upstream = await forward_to_upstream(server, "tools/list", body, authorization)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
        logger.error("mcp_upstream_unreachable", server_id=str(server_id), error=str(exc))
        return {**UPSTREAM_UNREACHABLE, "id": body.get("id")}

    if not server.approved_tools:
        return upstream

    tools = upstream.get("result", {}).get("tools", [])
    filtered = [t for t in tools if t["name"] in server.approved_tools]
    upstream["result"]["tools"] = filtered
    return upstream


@router.post("/{server_id}/call_tool")
async def call_tool(
    server_id: uuid.UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(require_gateway_agent),
    authorization: Optional[str] = Header(default=None),
) -> dict:
    server = await _get_server(db, server_id)
    params = body.get("params", {})
    tool_name = params.get("name")
    tool_arguments = params.get("arguments", {})

    try:
        session_id = uuid.UUID(params["session_id"])
    except (KeyError, ValueError, TypeError):
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "error": {"code": -32602, "message": "Invalid params: session_id is required"}}

    if server.approved_tools and tool_name not in server.approved_tools:
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "result": {"content": [{"type": "text", "text": "Denied: tool not in this server's approved list"}], "isError": True}}

    agent_id = uuid.UUID(token["agent_id"])
    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = agent_result.scalar_one_or_none()
    # session_id comes from the caller (params.session_id, required) so every
    # tool call in one workflow run shares the same session for rate-limit/
    # budget accumulation — not minted fresh per call (session-semantics
    # decision, plan 02 Task 4).

    gov_result = await evaluate_tool_call(
        db, agent=agent, agent_name=agent.name if agent else str(agent_id),
        tool_name=tool_name, tool_parameters=tool_arguments,
        workflow="mcp_gateway", session_id=session_id,
    )

    await ensure_session(db, session_id, agent_id)
    await accumulate_session_risk(db, session_id, RISK_SCORE_DELTA.get(gov_result.decision, 0))

    if gov_result.decision == "review":
        # Mirrors app/routers/intercept.py's review branch: a review decision
        # must produce a pending HITLReview row and a Slack notification
        # attempt, not the same hard-deny response as an actual `deny`. This
        # writes synchronously (not through the WAL) because create_hitl_review
        # needs a real audit_events.id FK to exist first.
        event_id = await write_event(
            session=db, session_id=session_id, agent_id=agent_id,
            agent_name=agent.name if agent else str(agent_id),
            tool_name=tool_name, tool_parameters=tool_arguments,
            decision="review", decision_reason=gov_result.reason,
            workflow="mcp_gateway", sequence_number=0, duration_ms=0,
            risk_delta=RISK_SCORE_DELTA.get("review", 0),
            policy_name=gov_result.fired_policy_name,
            policy_id=uuid.UUID(gov_result.fired_policy_id) if gov_result.fired_policy_id else None,
        )
        review_id = await create_hitl_review(session=db, audit_event_id=event_id, session_id=session_id)
        import asyncio
        asyncio.create_task(post_slack_review(
            review_id=review_id, audit_event_id=event_id,
            agent_name=agent.name if agent else str(agent_id),
            tool_name=tool_name, tool_parameters=tool_arguments,
            decision_reason=gov_result.reason,
        ))
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "result": {"content": [{"type": "text", "text": f"Pending human review: {gov_result.reason}"}], "isError": True}}

    if gov_result.decision != "allow":
        wal_writer.append({
            "session_id": str(session_id), "agent_id": str(agent_id),
            "agent_name": agent.name if agent else str(agent_id),
            "tool_name": tool_name, "tool_parameters": tool_arguments,
            "decision": gov_result.decision, "decision_reason": gov_result.reason,
            "policy_id": gov_result.fired_policy_id, "policy_name": gov_result.fired_policy_name,
            "sequence_number": 0, "duration_ms": 0,
            "risk_delta": RISK_SCORE_DELTA.get(gov_result.decision, 0),
            "bypass": gov_result.bypass, "enforced": True,
        })
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "result": {"content": [{"type": "text", "text": f"Denied by policy: {gov_result.reason}"}], "isError": True}}

    try:
        upstream_response = await forward_to_upstream(server, "tools/call", body, authorization)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
        logger.error("mcp_upstream_unreachable", server_id=str(server_id), error=str(exc))
        return {**UPSTREAM_UNREACHABLE, "id": body.get("id")}

    scan_result = scan_tool_response(upstream_response.get("result"), tool_name)
    decision, reason = ("deny", f"response_scan_flagged:{','.join(t.category for t in scan_result.threats)}") if not scan_result.is_safe else ("allow", "response_scan_clean")

    wal_writer.append({
        "session_id": str(session_id), "agent_id": str(agent_id),
        "agent_name": agent.name if agent else str(agent_id),
        "tool_name": tool_name, "tool_parameters": tool_arguments,
        "decision": decision, "decision_reason": reason,
        "policy_id": gov_result.fired_policy_id, "policy_name": gov_result.fired_policy_name,
        "sequence_number": 0, "duration_ms": 0,
        "risk_delta": RISK_SCORE_DELTA.get(decision, 0),
        "bypass": gov_result.bypass, "enforced": True,
    })

    if decision != "allow":
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "result": {"content": [{"type": "text", "text": "Blocked: response scan flagged this tool's output as unsafe."}], "isError": True}}

    return upstream_response
