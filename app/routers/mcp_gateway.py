"""In-process MCP gateway (Decision 12, plans/2026-09-07-gateway-pivot.md).
Agents point their MCP client at /mcp/{server_id}/... instead of self-reporting
to /intercept. Rebuilds the shape of the deleted enterprise/mcp_gateway/
against Cedar (via app.services.governance_engine) instead of OPA, and fixes
its three known gaps: unauthenticated ingress (Task 2's require_gateway_agent),
unvalidated agent_id claims (same fix — identity comes only from the token),
and fail-open on unreachable downstream (explicit JSON-RPC error, this task).
"""
import json
import time
import uuid
from typing import Any, Optional
from urllib.parse import urlparse

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
from app.services.governance_engine import evaluate_and_enforce
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


def _downstream_http_error_response(exc: "httpx.HTTPStatusError", request_id: Any) -> dict:
    """A downstream server that responded (a real 4xx/5xx) is a distinct
    failure mode from one that never responded at all (ConnectError/Timeout)
    — collapsing both into UPSTREAM_UNREACHABLE lost the real status/detail
    a caller needs to debug a misconfigured or failing downstream server."""
    status_code = exc.response.status_code
    detail = exc.response.text[:500]
    return {
        "jsonrpc": "2.0", "id": request_id,
        "error": {
            "code": -32001,
            "message": f"Downstream MCP server returned HTTP {status_code}",
            "data": {"status_code": status_code, "detail": detail},
        },
    }


def enrich_parameters(tool_name: str, tool_parameters: dict[str, Any]) -> dict[str, Any]:
    """Enrich tool_parameters before persisting. Extracts domain from HTTP tool URLs.
    Ported from app/routers/intercept.py (deleted by plan 04) rather than imported
    from it, since this router must not depend on a module scheduled for deletion.
    Audit-only: Cedar policy evaluation sees raw tool_arguments in both routers."""
    params = dict(tool_parameters)
    if tool_name in ("http_get", "http_post", "http_put", "http_delete", "http_patch"):
        url = params.get("url", "")
        if url and isinstance(url, (str, bytes)):
            # urlparse raises AttributeError for a non-str/bytes url (e.g. a
            # caller sending {"url": 123}) -- this runs before any audit
            # write, so an uncaught exception here used to drop the call's
            # audit trail entirely (3.6 fix).
            try:
                parsed = urlparse(url)
            except (AttributeError, TypeError, ValueError):
                parsed = None
            if parsed is not None and parsed.netloc:
                params["domain"] = parsed.netloc
    return params


async def _audit_malformed_call_tool_request(
    db: AsyncSession,
    agent_id: uuid.UUID,
    session_id: Optional[uuid.UUID],
    sequence_number: Optional[int],
    tool_name: Optional[str],
    workflow: str,
    reason: str,
    start: float,
) -> None:
    """A malformed call_tool request (missing/invalid tool_name, session_id,
    or sequence_number) used to return before any audit write, leaving zero
    trace -- contradicting the permanent constraint that every intercept
    writes an audit_event regardless of decision. session_id/agent_id are
    nullable on AuditEvent, so this writes even when session_id itself is
    the missing/invalid field."""
    if session_id is not None:
        await ensure_session(db, session_id, agent_id)
    wal_writer.append({
        "session_id": str(session_id) if session_id is not None else None,
        "agent_id": str(agent_id),
        "agent_name": str(agent_id),
        "tool_name": tool_name if isinstance(tool_name, str) and tool_name else "<missing>",
        "tool_parameters": {},
        "decision": "deny", "decision_reason": f"malformed_request:{reason}",
        "workflow": workflow,
        "policy_id": None, "policy_name": None,
        "sequence_number": sequence_number if sequence_number is not None else 0,
        "duration_ms": int((time.monotonic() - start) * 1000),
        "risk_delta": 0,
        "input_tokens": None, "output_tokens": None, "cost_usd": None,
        "bypass": False, "enforced": True,
    })


async def _get_server(db: AsyncSession, server_id: uuid.UUID) -> MCPServer:
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not registered")
    if server.status != "active":
        raise HTTPException(status_code=403, detail=f"MCP server status is '{server.status}', not 'active'")
    return server


def _parse_mcp_response(response: httpx.Response) -> dict:
    """The MCP Streamable HTTP transport spec allows a server to reply with
    either application/json or an SSE-framed text/event-stream body (one
    "data: <json>" event per message) -- response.json() raises
    JSONDecodeError on the latter. A spec-compliant server (verified against
    the public DeepWiki MCP server) uses text/event-stream for every
    response once the caller declares it in Accept, which this gateway must,
    so this path is not a corner case."""
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        for line in response.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[len("data:"):].strip())
        raise ValueError("SSE response from downstream MCP server contained no data event")
    return response.json()


async def forward_to_upstream(server: MCPServer, method: str, body: dict, auth_header: Optional[str]) -> dict:
    """Forward a JSON-RPC request to the registered downstream server.
    Pure passthrough (Decision 9): auth_header is whatever the gateway
    caller's own Authorization header carried, forwarded unchanged. No
    credential is read from or written to the MCPServer row.
    Accept must declare both application/json and text/event-stream -- the
    MCP Streamable HTTP transport spec requires it, and a spec-compliant
    server (e.g. DeepWiki) returns HTTP 406 for any request missing it,
    failing every real tool call before it reaches the downstream tool."""
    headers = {"Accept": "application/json, text/event-stream"}
    if auth_header:
        headers["Authorization"] = auth_header
    outgoing = {**body, "method": method}
    async with httpx.AsyncClient() as client:
        response = await client.post(server.base_url, json=outgoing, headers=headers, timeout=10.0)
        response.raise_for_status()
        return _parse_mcp_response(response)


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
    except httpx.HTTPStatusError as exc:
        logger.error("mcp_upstream_http_error", server_id=str(server_id),
                     status_code=exc.response.status_code, error=str(exc))
        return _downstream_http_error_response(exc, body.get("id"))
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
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
    start = time.monotonic()
    params = body.get("params", {})
    tool_name = params.get("name")
    tool_arguments = params.get("arguments", {})
    agent_id = uuid.UUID(token["agent_id"])
    workflow = params.get("workflow") or "unassigned"

    try:
        server = await _get_server(db, server_id)
    except HTTPException as exc:
        # _get_server used to raise before any audit write, leaving zero
        # trace for a call against a deleted/never-registered/suspended
        # server despite a valid gateway-agent token -- same gap the
        # malformed-request paths below were patched to close.
        await _audit_malformed_call_tool_request(
            db, agent_id, None, None, tool_name, workflow,
            f"server_unavailable:{exc.detail}", start)
        raise

    if not tool_name or not isinstance(tool_name, str):
        await _audit_malformed_call_tool_request(
            db, agent_id, None, None, tool_name, workflow, "missing_tool_name", start)
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "error": {"code": -32602, "message": "Invalid params: name is required"}}

    try:
        session_id = uuid.UUID(params["session_id"])
    except (KeyError, ValueError, TypeError):
        await _audit_malformed_call_tool_request(
            db, agent_id, None, None, tool_name, workflow, "missing_session_id", start)
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "error": {"code": -32602, "message": "Invalid params: session_id is required"}}

    # Mandatory, matching /intercept.py's InterceptRequest.sequence_number
    # (required, no default) -- not generated, since only the caller knows
    # its own per-session call ordering.
    try:
        sequence_number = int(params["sequence_number"])
    except (KeyError, ValueError, TypeError):
        await _audit_malformed_call_tool_request(
            db, agent_id, session_id, None, tool_name, workflow, "missing_sequence_number", start)
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "error": {"code": -32602, "message": "Invalid params: sequence_number is required"}}

    # Optional, defaulted the same way /intercept.py's InterceptRequest.workflow
    # is: no active policy conditions on workflow today (verified against
    # policies/ and policy_compiler.py), so this stays a grouping dimension,
    # not an enforcement input.
    input_tokens = params.get("input_tokens")
    output_tokens = params.get("output_tokens")
    cost_usd = params.get("cost_usd")

    enriched_arguments = enrich_parameters(tool_name, tool_arguments)

    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = agent_result.scalar_one_or_none()
    # session_id comes from the caller (params.session_id, required) so every
    # tool call in one workflow run shares the same session for rate-limit/
    # budget accumulation — not minted fresh per call (session-semantics
    # decision, plan 02 Task 4).

    if server.approved_tools and tool_name not in server.approved_tools:
        # Every intercept writes an audit_event regardless of decision
        # (Permanent Constraint) — this gate used to return before that,
        # leaving server-scope denies with zero trace in the audit trail.
        await ensure_session(db, session_id, agent_id)
        wal_writer.append({
            "session_id": str(session_id), "agent_id": str(agent_id),
            "agent_name": agent.name if agent else str(agent_id),
            "tool_name": tool_name, "tool_parameters": enriched_arguments,
            "decision": "deny", "decision_reason": "server_approved_tools_gate",
            "workflow": workflow,
            "policy_id": None, "policy_name": None,
            "sequence_number": sequence_number, "duration_ms": int((time.monotonic() - start) * 1000),
            "risk_delta": RISK_SCORE_DELTA.get("deny", 0),
            "input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost_usd,
            "bypass": False, "enforced": True,
        })
        await accumulate_session_risk(db, session_id, RISK_SCORE_DELTA.get("deny", 0))
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "result": {"content": [{"type": "text", "text": "Denied: tool not in this server's approved list"}], "isError": True}}

    # evaluate_and_enforce (app/services/governance_engine.py) is the single
    # shared enforcement path with app/routers/intercept.py: agent-level
    # approved_tools gate, observe-mode decision collapse, budget-threshold
    # alerting, and bypass logging all live there now, not duplicated here.
    try:
        gov_result = await evaluate_and_enforce(
            db, agent=agent, agent_id=agent_id, agent_name=agent.name if agent else str(agent_id),
            tool_name=tool_name, tool_parameters=tool_arguments,
            workflow=workflow, session_id=session_id,
        )
    except Exception as exc:
        # Unlike cedar_client.evaluate()'s own fail-closed try/except, the
        # rest of the pipeline it's wrapped in (get_scoped_policies,
        # build_call_counts, build_token_budgets, build_aggregate_budgets)
        # was unguarded -- a transient DB error there used to propagate to
        # an unhandled 500 with zero audit_event, instead of failing closed
        # like every other error path in this router.
        logger.error("governance_pipeline_failed", agent_id=str(agent_id),
                     tool_name=tool_name, error=str(exc))
        await ensure_session(db, session_id, agent_id)
        wal_writer.append({
            "session_id": str(session_id), "agent_id": str(agent_id),
            "agent_name": agent.name if agent else str(agent_id),
            "tool_name": tool_name, "tool_parameters": enriched_arguments,
            "decision": "deny", "decision_reason": f"evaluation_pipeline_error:{type(exc).__name__}",
            "workflow": workflow,
            "policy_id": None, "policy_name": None,
            "sequence_number": sequence_number, "duration_ms": int((time.monotonic() - start) * 1000),
            "risk_delta": RISK_SCORE_DELTA.get("deny", 0),
            "input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost_usd,
            "bypass": False, "enforced": True,
        })
        await accumulate_session_risk(db, session_id, RISK_SCORE_DELTA.get("deny", 0))
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "result": {"content": [{"type": "text", "text": "Denied: governance evaluation failed"}], "isError": True}}

    await ensure_session(db, session_id, agent_id)
    await accumulate_session_risk(db, session_id, RISK_SCORE_DELTA.get(gov_result.decision, 0))

    if gov_result.decision == "review" and not gov_result.is_observe_mode:
        # Mirrors app/routers/intercept.py's review branch: a review decision
        # must produce a pending HITLReview row and a Slack notification
        # attempt, not the same hard-deny response as an actual `deny`. This
        # writes synchronously (not through the WAL) because create_hitl_review
        # needs a real audit_events.id FK to exist first.
        event_id = await write_event(
            session=db, session_id=session_id, agent_id=agent_id,
            agent_name=agent.name if agent else str(agent_id),
            tool_name=tool_name, tool_parameters=enriched_arguments,
            decision="review", decision_reason=gov_result.reason,
            workflow=workflow, sequence_number=sequence_number,
            duration_ms=int((time.monotonic() - start) * 1000),
            risk_delta=RISK_SCORE_DELTA.get("review", 0),
            policy_name=gov_result.fired_policy_name,
            policy_id=uuid.UUID(gov_result.fired_policy_id) if gov_result.fired_policy_id else None,
            input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost_usd,
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
                "result": {"content": [{"type": "text", "text": f"Pending human review: {gov_result.reason}"}], "isError": True,
                           "_meta": {"review_id": str(review_id)}}}

    if gov_result.decision != "allow":
        # Written even when observe mode collapses enforced_decision to
        # "allow" below -- the true decision must still show up in the audit
        # trail (matching /intercept), just marked not enforced.
        wal_writer.append({
            "session_id": str(session_id), "agent_id": str(agent_id),
            "agent_name": agent.name if agent else str(agent_id),
            "tool_name": tool_name, "tool_parameters": enriched_arguments,
            "decision": gov_result.decision, "decision_reason": gov_result.reason,
            "workflow": workflow,
            "policy_id": gov_result.fired_policy_id, "policy_name": gov_result.fired_policy_name,
            "sequence_number": sequence_number, "duration_ms": int((time.monotonic() - start) * 1000),
            "risk_delta": RISK_SCORE_DELTA.get(gov_result.decision, 0),
            "input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost_usd,
            "bypass": gov_result.bypass, "enforced": not gov_result.is_observe_mode,
        })

    if gov_result.enforced_decision != "allow":
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "result": {"content": [{"type": "text", "text": f"Denied by policy: {gov_result.reason}"}], "isError": True}}

    try:
        upstream_response = await forward_to_upstream(server, "tools/call", body, authorization)
    except httpx.HTTPStatusError as exc:
        logger.error("mcp_upstream_http_error", server_id=str(server_id),
                     status_code=exc.response.status_code, error=str(exc))
        # gov_result.decision == "allow" here (enforced_decision check above
        # already returned for any non-allow case) — without this write, an
        # allowed call that fails downstream left zero audit_event, violating
        # "every intercept writes an audit_event regardless of decision".
        wal_writer.append({
            "session_id": str(session_id), "agent_id": str(agent_id),
            "agent_name": agent.name if agent else str(agent_id),
            "tool_name": tool_name, "tool_parameters": enriched_arguments,
            "decision": "allow", "decision_reason": f"upstream_http_error:{exc.response.status_code}",
            "workflow": workflow,
            "policy_id": gov_result.fired_policy_id, "policy_name": gov_result.fired_policy_name,
            "sequence_number": sequence_number, "duration_ms": int((time.monotonic() - start) * 1000),
            "risk_delta": 0,
            "input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost_usd,
            "bypass": gov_result.bypass, "enforced": True,
        })
        return _downstream_http_error_response(exc, body.get("id"))
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.error("mcp_upstream_unreachable", server_id=str(server_id), error=str(exc))
        wal_writer.append({
            "session_id": str(session_id), "agent_id": str(agent_id),
            "agent_name": agent.name if agent else str(agent_id),
            "tool_name": tool_name, "tool_parameters": enriched_arguments,
            "decision": "allow", "decision_reason": "upstream_unreachable",
            "workflow": workflow,
            "policy_id": gov_result.fired_policy_id, "policy_name": gov_result.fired_policy_name,
            "sequence_number": sequence_number, "duration_ms": int((time.monotonic() - start) * 1000),
            "risk_delta": 0,
            "input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost_usd,
            "bypass": gov_result.bypass, "enforced": True,
        })
        return {**UPSTREAM_UNREACHABLE, "id": body.get("id")}

    if isinstance(upstream_response.get("error"), dict):
        # httpx's raise_for_status() only catches HTTP-level failures -- a
        # JSON-RPC error body (still HTTP 200) reaches here as a normal
        # upstream_response. Without this branch it fell through to the scan
        # below, which sees result=None, calls that "clean", and audits the
        # call as decision=allow/response_scan_clean -- indistinguishable
        # from a real successful call in the audit trail.
        error_code = upstream_response["error"].get("code")
        wal_writer.append({
            "session_id": str(session_id), "agent_id": str(agent_id),
            "agent_name": agent.name if agent else str(agent_id),
            "tool_name": tool_name, "tool_parameters": enriched_arguments,
            "decision": "error", "decision_reason": f"upstream_jsonrpc_error:{error_code}",
            "workflow": workflow,
            "policy_id": gov_result.fired_policy_id, "policy_name": gov_result.fired_policy_name,
            "sequence_number": sequence_number, "duration_ms": int((time.monotonic() - start) * 1000),
            "risk_delta": 0,
            "input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost_usd,
            "bypass": gov_result.bypass, "enforced": True,
        })
        return upstream_response

    scan_result = await scan_tool_response(upstream_response.get("result"), tool_name)
    decision, reason = ("deny", f"response_scan_flagged:{','.join(t.category for t in scan_result.threats)}") if not scan_result.is_safe else ("allow", "response_scan_clean")

    wal_writer.append({
        "session_id": str(session_id), "agent_id": str(agent_id),
        "agent_name": agent.name if agent else str(agent_id),
        "tool_name": tool_name, "tool_parameters": enriched_arguments,
        "decision": decision, "decision_reason": reason,
        "workflow": workflow,
        "policy_id": gov_result.fired_policy_id, "policy_name": gov_result.fired_policy_name,
        "sequence_number": sequence_number, "duration_ms": int((time.monotonic() - start) * 1000),
        "risk_delta": RISK_SCORE_DELTA.get(decision, 0),
        "input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost_usd,
        "bypass": gov_result.bypass, "enforced": True,
    })

    if decision != "allow":
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "result": {"content": [{"type": "text", "text": "Blocked: response scan flagged this tool's output as unsafe."}], "isError": True}}

    return upstream_response
