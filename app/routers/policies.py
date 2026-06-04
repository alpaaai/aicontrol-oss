"""Policy CRUD endpoints — admin only."""
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
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


def validate_tool_denylist_condition(condition: dict) -> list[str]:
    blocked = condition.get("blocked_tools", [])
    if not isinstance(blocked, list) or not blocked:
        return ["tool_denylist condition requires non-empty 'blocked_tools' array"]
    if not all(isinstance(t, str) for t in blocked):
        return ["tool_denylist.blocked_tools must be an array of strings"]
    return []


def validate_parameter_match_condition(condition: dict) -> list[str]:
    pm = condition.get("parameter_match", {})
    if not pm or not isinstance(pm, dict):
        return ["parameter_match condition requires non-empty 'parameter_match' object"]
    errors: list[str] = []
    for key, spec in pm.items():
        if not isinstance(spec, dict):
            errors.append(
                f"parameter_match[{key!r}] must be an object with 'contains_any' or 'equals'"
            )
            continue
        has_contains = "contains_any" in spec
        has_equals = "equals" in spec
        if not has_contains and not has_equals:
            errors.append(
                f"parameter_match[{key!r}] must have 'contains_any' (list) or 'equals' (string)"
            )
        if has_contains and not isinstance(spec["contains_any"], list):
            errors.append(f"parameter_match[{key!r}].contains_any must be an array")
    return errors


def validate_tool_pattern_condition(condition: dict) -> list[str]:
    patterns = condition.get("tool_name_contains", [])
    if not isinstance(patterns, list) or not patterns:
        return ["tool_pattern condition requires non-empty 'tool_name_contains' array"]
    return []


VALID_NUMERIC_OPS = {">", ">=", "<", "<=", "=="}


def validate_numeric_conditions_condition(condition: dict) -> list[str]:
    nc = condition.get("numeric_conditions", {})
    if not nc or not isinstance(nc, dict):
        return ["numeric_conditions requires non-empty 'numeric_conditions' object"]
    errors: list[str] = []
    for field, spec in nc.items():
        if not isinstance(spec, dict):
            errors.append(
                f"numeric_conditions[{field!r}] must be an object with 'op' and 'value'"
            )
            continue
        if spec.get("op") not in VALID_NUMERIC_OPS:
            errors.append(
                f"numeric_conditions[{field!r}].op must be one of {sorted(VALID_NUMERIC_OPS)}"
            )
        if "value" not in spec or not isinstance(spec.get("value"), (int, float)):
            errors.append(f"numeric_conditions[{field!r}].value must be a number")
    return errors


def validate_condition(rule_type: str, condition: dict) -> list[str]:
    if rule_type == "tool_denylist":
        return validate_tool_denylist_condition(condition)
    if rule_type == "parameter_match":
        return validate_parameter_match_condition(condition)
    if rule_type == "rate_limit":
        return validate_rate_limit_condition(condition)
    if rule_type == "tool_pattern":
        return validate_tool_pattern_condition(condition)
    if rule_type == "numeric_conditions":
        return validate_numeric_conditions_condition(condition)
    return []


class PolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rule_type: str
    condition: dict[str, Any]
    action: str
    severity: str = "medium"
    compliance_frameworks: list[str] = []
    priority: int = 100
    library: bool = False
    category: Optional[str] = None


class PolicyUpdate(BaseModel):
    description: Optional[str] = None
    rule_type: Optional[str] = None
    condition: Optional[dict[str, Any]] = None
    action: Optional[str] = None
    severity: Optional[str] = None
    active: Optional[bool] = None
    compliance_frameworks: Optional[list[str]] = None
    priority: Optional[int] = None
    library: Optional[bool] = None
    category: Optional[str] = None


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
    applies_to_agents: int = 0
    created_by: Optional[str] = None
    priority: int = 100
    library: bool = False
    category: Optional[str] = None

    class Config:
        from_attributes = True

    @field_validator("applies_to_agents", mode="before")
    @classmethod
    def _coerce_list_to_count(cls, v: Any) -> int:
        if isinstance(v, list):
            return len(v)
        if isinstance(v, int):
            return v
        return 0


@router.get("", response_model=list[PolicyResponse])
async def list_policies(
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> list[PolicyResponse]:
    result = await db.execute(select(Policy).order_by(Policy.priority, Policy.name))
    return result.scalars().all()


@router.get("/library", response_model=list[PolicyResponse])
async def list_library_policies(
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> list[PolicyResponse]:
    result = await db.execute(
        select(Policy)
        .where(Policy.library == True)
        .order_by(Policy.priority, Policy.name)
    )
    return result.scalars().all()


STANDARD_BASELINE_NAMES = [
    "block_shell_execution",
    "block_file_deletion",
    "block_cloud_metadata_access",
    "block_sensitive_file_reads",
]

STRICT_ADDITIONAL_NAMES = [
    "block_wildcard_queries",
    "block_large_record_exports",
    "block_prompt_injection_in_params",
    "block_credential_patterns",
]


class BaselineActivateBody(BaseModel):
    mode: str

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, v: str) -> str:
        if v not in {"standard", "strict"}:
            raise ValueError("mode must be 'standard' or 'strict'")
        return v


class BaselineActivateResponse(BaseModel):
    mode: str
    activated: list[str]


@router.post("/activate-baseline", response_model=BaselineActivateResponse)
async def activate_baseline(
    body: BaselineActivateBody,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> BaselineActivateResponse:
    names = list(STANDARD_BASELINE_NAMES)
    if body.mode == "strict":
        names = names + STRICT_ADDITIONAL_NAMES

    result = await db.execute(
        select(Policy).where(Policy.name.in_(names))
    )
    policies = result.scalars().all()

    activated: list[str] = []
    for policy in policies:
        policy.active = True
        activated.append(policy.name)

    await db.flush()
    await push_rego_to_opa()
    return BaselineActivateResponse(mode=body.mode, activated=activated)


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
    errors = validate_condition(body.rule_type, body.condition)
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
        priority=body.priority,
        library=body.library,
        category=body.category,
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
    token: dict = Depends(require_admin),
) -> PolicyResponse:
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    updated = body.model_dump(exclude_none=True)
    effective_rule_type = updated.get("rule_type", policy.rule_type)
    effective_condition = updated.get("condition", policy.condition)
    errors = validate_condition(effective_rule_type, effective_condition)
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
        user_email=token.get("email"),
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
