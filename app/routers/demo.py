"""Demo runner endpoints — seed/reset demo data, issue demo token."""
import json
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.auth import create_token, hash_token, require_admin
from app.core.config import settings
from app.models.database import get_db

router = APIRouter(prefix="/demo", tags=["demo"])

# Agent UUIDs seeded for all industry demo scenarios.
DEMO_AGENT_IDS = [
    "00000000-0000-0000-0000-000000000010",  # loan-underwriting-agent
    "00000000-0000-0000-0000-000000000020",  # clinical-documentation-agent
    "00000000-0000-0000-0000-000000000030",  # incident-response-agent
    "00000000-0000-0000-0000-000000000040",  # supplier-sourcing-agent
    "00000000-0000-0000-0000-000000000050",  # support-resolution-agent
    "00000000-0000-0000-0000-000000000060",  # crm-automation-agent
    "00000000-0000-0000-0000-000000000070",  # insurance-claims-agent
]

DEMO_AGENTS = [
    {
        "id": "00000000-0000-0000-0000-000000000010",
        "name": "loan-underwriting-agent",
        "owner": "lending-team@bank.com",
        "status": "active",
        "tools": json.dumps([
            "query_credit_bureau", "run_risk_model", "get_income_verification",
            "get_employment_history", "approve_loan", "deny_loan",
        ]),
    },
    {
        "id": "00000000-0000-0000-0000-000000000020",
        "name": "clinical-documentation-agent",
        "owner": "clinical-ops@hospital.org",
        "status": "active",
        "tools": json.dumps([
            "read_patient_record", "write_soap_note", "get_lab_results",
            "get_medication_list", "schedule_followup",
        ]),
    },
    {
        "id": "00000000-0000-0000-0000-000000000030",
        "name": "incident-response-agent",
        "owner": "platform-ops@company.com",
        "status": "active",
        "tools": json.dumps([
            "get_incident_details", "update_incident_status", "assign_ticket",
            "get_runbook", "restart_service", "send_notification",
        ]),
    },
    {
        "id": "00000000-0000-0000-0000-000000000040",
        "name": "supplier-sourcing-agent",
        "owner": "procurement@manufacturer.com",
        "status": "active",
        "tools": json.dumps([
            "query_inventory_system", "query_approved_supplier_catalog",
            "create_purchase_order", "get_supplier_quote",
        ]),
    },
    {
        "id": "00000000-0000-0000-0000-000000000050",
        "name": "support-resolution-agent",
        "owner": "cx-platform@company.com",
        "status": "active",
        "tools": json.dumps([
            "read_customer_account", "update_ticket_status", "send_email",
            "create_refund", "escalate_ticket",
        ]),
    },
    {
        "id": "00000000-0000-0000-0000-000000000060",
        "name": "crm-automation-agent",
        "owner": "revops@company.com",
        "status": "active",
        "tools": json.dumps([
            "update_deal_stage", "log_sales_activity", "get_account_details",
            "create_task", "send_follow_up",
        ]),
    },
    {
        "id": "00000000-0000-0000-0000-000000000070",
        "name": "insurance-claims-agent",
        "owner": "claims-ops@aon.com",
        "status": "active",
        "tools": json.dumps([
            "get_claim_details", "validate_policy_coverage", "process_claim_payment",
            "request_additional_info", "flag_for_review",
        ]),
    },
]

_DEMO_TOKEN_DESCRIPTION = "demo-dashboard"


async def _upsert_demo_agents(db: AsyncSession) -> None:
    for agent in DEMO_AGENTS:
        await db.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools)
            VALUES (:id, :name, :owner, :status, CAST(:tools AS jsonb))
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                status = 'active',
                approved_tools = EXCLUDED.approved_tools
        """), agent)
    await db.commit()


async def _issue_demo_token(db: AsyncSession) -> str:
    """Delete old demo-dashboard tokens and issue a fresh one. Returns the raw JWT."""
    await db.execute(text(
        "DELETE FROM api_tokens WHERE description = :desc"
    ), {"desc": _DEMO_TOKEN_DESCRIPTION})
    token = create_token(role="agent", description=_DEMO_TOKEN_DESCRIPTION)
    await db.execute(text("""
        INSERT INTO api_tokens (id, token_hash, role, description, revoked)
        VALUES (gen_random_uuid(), :hash, 'agent', :desc, false)
    """), {"hash": hash_token(token), "desc": _DEMO_TOKEN_DESCRIPTION})
    await db.commit()
    return token


class StatusResponse(BaseModel):
    seeded: bool
    demo_token: Optional[str]


class SeedResponse(BaseModel):
    ok: bool
    demo_token: str


class ResetResponse(BaseModel):
    ok: bool


@router.get("/status", response_model=StatusResponse)
async def get_demo_status(
    _: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> StatusResponse:
    result = await db.execute(text(
        "SELECT COUNT(*) FROM agents WHERE id = ANY(:ids)"
    ), {"ids": DEMO_AGENT_IDS})
    count = result.scalar() or 0
    seeded = count >= len(DEMO_AGENT_IDS)
    demo_token = settings.DEMO_TOKEN if settings.DEMO_TOKEN else None
    return StatusResponse(seeded=seeded, demo_token=demo_token)


@router.post("/seed", response_model=SeedResponse)
async def seed_demo(
    _: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SeedResponse:
    await _upsert_demo_agents(db)
    if settings.DEMO_TOKEN:
        demo_token = settings.DEMO_TOKEN
    else:
        demo_token = await _issue_demo_token(db)
    return SeedResponse(ok=True, demo_token=demo_token)


@router.post("/reset", response_model=ResetResponse)
async def reset_demo(
    _: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ResetResponse:
    agent_ids = DEMO_AGENT_IDS
    await db.execute(text(
        "DELETE FROM hitl_reviews WHERE session_id IN "
        "(SELECT id FROM sessions WHERE agent_id = ANY(:ids))"
    ), {"ids": agent_ids})
    await db.execute(text(
        "DELETE FROM audit_events WHERE agent_id = ANY(:ids)"
    ), {"ids": agent_ids})
    await db.execute(text(
        "DELETE FROM sessions WHERE agent_id = ANY(:ids)"
    ), {"ids": agent_ids})
    await db.commit()
    await _upsert_demo_agents(db)
    return ResetResponse(ok=True)
