"""Policy CRUD endpoints — admin only."""
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.models.database import get_db
from app.models.schemas import Policy
from app.services.activity_log_service import write_activity_log
from app.services.policy_loader import push_rego_to_opa

router = APIRouter(prefix="/policies", tags=["policies"])

VALID_WINDOWS = {"session", "5m", "60m", "24h", "7d"}
VALID_ON_EXCEED = {"deny", "review"}


def validate_rate_limit_condition(condition: dict) -> list[str]:
    errors = []
    rl = condition.get("rate_limit", {})
    tools = condition.get("tools", [])

    if not tools or not isinstance(tools, list):
        errors.append("rate_limit condition requires non-empty 'tools' array")

    max_calls = rl.get("max_calls")
    if not isinstance(max_calls, int) or max_calls < 1:
        errors.append("rate_limit.max_calls must be a positive integer")

    window = rl.get("window")
    if window not in VALID_WINDOWS:
        errors.append(
            f"rate_limit.window must be one of: {', '.join(sorted(VALID_WINDOWS))}"
        )

    on_exceed = rl.get("on_exceed", "deny")
    if on_exceed not in VALID_ON_EXCEED:
        errors.append("rate_limit.on_exceed must be 'deny' or 'review'")

    return errors


class PolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rule_type: str
    condition: dict[str, Any]
    action: str
    severity: str = "medium"
    compliance_frameworks: list[str] = []


class PolicyUpdate(BaseModel):
    description: Optional[str] = None
    rule_type: Optional[str] = None
    condition: Optional[dict[str, Any]] = None
    action: Optional[str] = None
    severity: Optional[str] = None
    active: Optional[bool] = None
    compliance_frameworks: Optional[list[str]] = None


class PolicyResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    rule_type: str
    condition: dict[str, Any]
    action: str
    severity: Optional[str]
    active: Optional[bool]
    compliance_frameworks: Optional[list]

    class Config:
        from_attributes = True


@router.get("", response_model=list[PolicyResponse])
async def list_policies(
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> list[PolicyResponse]:
    result = await db.execute(select(Policy).order_by(Policy.name))
    return result.scalars().all()


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> PolicyResponse:
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.post("", response_model=PolicyResponse, status_code=201)
async def create_policy(
    body: PolicyCreate,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> PolicyResponse:
    if body.rule_type == "rate_limit":
        errors = validate_rate_limit_condition(body.condition)
        if errors:
            raise HTTPException(status_code=422, detail="; ".join(errors))
    policy = Policy(
        name=body.name,
        description=body.description,
        rule_type=body.rule_type,
        condition=body.condition,
        action=body.action,
        severity=body.severity,
        compliance_frameworks=body.compliance_frameworks,
        active=True,
    )
    db.add(policy)
    await db.flush()
    await push_rego_to_opa()
    return policy


@router.put("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: uuid.UUID,
    body: PolicyUpdate,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> PolicyResponse:
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    updated = body.model_dump(exclude_none=True)
    effective_rule_type = updated.get("rule_type", policy.rule_type)
    effective_condition = updated.get("condition", policy.condition)
    if effective_rule_type == "rate_limit":
        errors = validate_rate_limit_condition(effective_condition)
        if errors:
            raise HTTPException(status_code=422, detail="; ".join(errors))
    before = {k: getattr(policy, k) for k in updated}
    for field, value in updated.items():
        setattr(policy, field, value)
    await db.flush()
    await push_rego_to_opa()
    await write_activity_log(
        action="policy.update",
        resource_type="policy",
        resource_id=str(policy_id),
        before_state=before,
        after_state=updated,
    )
    return policy


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> None:
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    await db.delete(policy)
    await push_rego_to_opa()
