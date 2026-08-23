"""Policy CRUD endpoints — admin only."""
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.models.database import get_db
from app.models.schemas import Policy
from app.services.activity_log_service import write_activity_log
from app.services.cedar_client import invalidate_policy_set_cache
from app.services.policy_compiler import compile_policy

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


def validate_token_budget_condition(condition: dict) -> list[str]:
    """blocked_tools presence is already covered by validate_tool_denylist_condition,
    which always runs first for tool_denylist policies — not duplicated here."""
    errors = []
    tb = condition.get("token_budget", {})
    if not tb.get("max_tokens") and not tb.get("max_cost_usd"):
        errors.append("token_budget condition requires 'max_tokens' or 'max_cost_usd'")
    window = tb.get("window")
    if window not in VALID_WINDOWS:
        errors.append(
            f"token_budget.window must be one of: {', '.join(sorted(VALID_WINDOWS))}"
        )
    on_exceed = tb.get("on_exceed", "deny")
    if on_exceed not in VALID_ON_EXCEED:
        errors.append("token_budget.on_exceed must be 'deny' or 'review'")
    return errors


def validate_parameter_match_condition(condition: dict) -> list[str]:
    pm = condition.get("parameter_match", {})
    if not pm or not isinstance(pm, dict):
        return ["parameter_match condition requires non-empty 'parameter_match' object"]
    errors: list[str] = []
    for key, spec in pm.items():
        if not isinstance(spec, dict):
            # A plain scalar is the base.rego spelling and stays valid: it means
            # exact equality, or a glob when it contains * or ?. Rejecting it
            # here would 422 every denylist policy that pins a parameter value,
            # which is most of the demo seeds.
            if isinstance(spec, (str, int, float, bool)) or spec is None:
                continue
            errors.append(
                f"parameter_match[{key!r}] must be a scalar, or an object with "
                "'contains_any' or 'equals'"
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


TOOL_DENYLIST_NUMERIC_OPS = {"gt", "gte", "lt", "lte", "eq"}


def validate_tool_denylist_numeric_conditions(condition: dict) -> list[str]:
    """tool_denylist's nested numeric_conditions is a LIST of {parameter, operator,
    value} dicts (unlike the standalone numeric_conditions rule_type's dict-of-dicts),
    and must use the operator strings base.rego's numeric_op_passes implements."""
    nc = condition.get("numeric_conditions")
    if not nc:
        return []
    if not isinstance(nc, list):
        return ["tool_denylist.numeric_conditions must be an array"]
    errors: list[str] = []
    for i, cond in enumerate(nc):
        if not isinstance(cond, dict):
            errors.append(f"numeric_conditions[{i}] must be an object")
            continue
        if not cond.get("parameter"):
            errors.append(f"numeric_conditions[{i}] requires 'parameter'")
        if cond.get("operator") not in TOOL_DENYLIST_NUMERIC_OPS:
            errors.append(
                f"numeric_conditions[{i}].operator must be one of "
                f"{sorted(TOOL_DENYLIST_NUMERIC_OPS)}, got {cond.get('operator')!r}"
            )
        if "value" not in cond or not isinstance(cond.get("value"), (int, float)):
            errors.append(f"numeric_conditions[{i}].value must be a number")
    return errors


def validate_tool_denylist_time_conditions(condition: dict) -> list[str]:
    """time_conditions must use the exact keys base.rego's day_is_denied/hour_is_denied
    read: deny_days (list of 0-6 ints) and/or deny_hours ({'from': int, 'to': int})."""
    tc = condition.get("time_conditions")
    if not tc:
        return []
    if not isinstance(tc, dict):
        return ["tool_denylist.time_conditions must be an object"]
    errors: list[str] = []
    known_keys = {"deny_days", "deny_hours"}
    unknown = set(tc.keys()) - known_keys
    if unknown:
        errors.append(
            f"time_conditions has unknown key(s) {sorted(unknown)}; "
            f"expected only {sorted(known_keys)}"
        )
    if "deny_days" in tc:
        days = tc["deny_days"]
        if not isinstance(days, list) or not all(
            isinstance(d, int) and 0 <= d <= 6 for d in days
        ):
            errors.append("time_conditions.deny_days must be a list of integers 0-6")
    if "deny_hours" in tc:
        dh = tc["deny_hours"]
        if not isinstance(dh, dict) or "from" not in dh or "to" not in dh:
            errors.append("time_conditions.deny_hours must be an object with 'from' and 'to'")
    return errors


def validate_condition(condition: dict) -> list[str]:
    """Validate a condition dict. Dispatch is by key presence and by shape, not
    by rule_type -- the same rule the compiler and the counting services follow."""
    errors: list[str] = []
    if "blocked_tools" in condition:
        errors += validate_tool_denylist_condition(condition)
    if "tool_name_contains" in condition:
        errors += validate_tool_pattern_condition(condition)
    if condition.get("token_budget"):
        errors += validate_token_budget_condition(condition)
    if condition.get("rate_limit"):
        errors += validate_rate_limit_condition(condition)
    if condition.get("parameter_match"):
        errors += validate_parameter_match_condition(condition)
    if "numeric_conditions" in condition:
        # Two shapes: the compact {"amount": {"op": ">", "value": 5}} object and
        # base.rego's [{"parameter", "operator", "value"}] list. Each has its own
        # operator vocabulary, so validate by shape.
        if isinstance(condition["numeric_conditions"], list):
            errors += validate_tool_denylist_numeric_conditions(condition)
        else:
            errors += validate_numeric_conditions_condition(condition)
    if condition.get("time_conditions"):
        errors += validate_tool_denylist_time_conditions(condition)
    return errors


def validate_scope(body: "PolicyCreate | PolicyUpdate", condition: dict) -> list[str]:
    """Reject a policy that constrains nothing.

    With no condition and no scope, compile_policy emits a bare
    `forbid (principal, action, resource);` -- which denies every tool call from
    every agent. Under Rego this was impossible to express by accident because a
    denylist needed a blocked_tools list; under the scope model it is one empty
    object away, so it is rejected explicitly.
    """
    # A token budget or rate limit that binds no tool would meter every tool the
    # policy's principal touches, which is never what the author meant. Under
    # Rego the tool list was structurally required; under the scope model the
    # binding can be action_tool instead, so accept either.
    if condition.get("token_budget") or condition.get("rate_limit"):
        bound = (
            getattr(body, "action_tool", None)
            or condition.get("blocked_tools")
            or condition.get("tools")
        )
        if not bound:
            return [
                "a token_budget or rate_limit condition must bind a tool, via "
                "action_tool or a blocked_tools/tools list"
            ]

    if condition:
        return []
    if any([
        getattr(body, "principal_id", None),
        getattr(body, "action_tool", None),
        getattr(body, "resource_system", None),
    ]):
        return []
    return [
        "a policy with no condition must constrain at least one of "
        "principal_id, action_tool or resource_system -- otherwise it denies "
        "every call from every agent"
    ]


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1)
    description: Optional[str] = None
    condition: dict[str, Any]
    # Cedar scope. NULL principal means "every agent", NULL action_tool "any
    # tool", NULL resource_system "any system".
    principal_type: Optional[str] = None
    principal_id: Optional[str] = None
    action_tool: Optional[str] = None
    resource_system: Optional[str] = None
    effect: str = "deny"
    severity: str = "medium"
    compliance_frameworks: list[str] = []
    priority: int = 100
    library: bool = False
    category: Optional[str] = None


class PolicyUpdate(BaseModel):
    description: Optional[str] = None
    condition: Optional[dict[str, Any]] = None
    principal_type: Optional[str] = None
    principal_id: Optional[str] = None
    action_tool: Optional[str] = None
    resource_system: Optional[str] = None
    effect: Optional[str] = None
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
    condition: dict[str, Any]
    principal_type: Optional[str] = None
    principal_id: Optional[str] = None
    action_tool: Optional[str] = None
    resource_system: Optional[str] = None
    effect: Optional[str] = None
    cedar_text: Optional[str] = None
    severity: Optional[str]
    active: Optional[bool]
    compliance_frameworks: Optional[list]
    created_by: Optional[str] = None
    priority: int = 100
    library: bool = False
    category: Optional[str] = None

    class Config:
        from_attributes = True



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
    invalidate_policy_set_cache()
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
    errors = validate_condition(body.condition) + validate_scope(body, body.condition)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))
    policy = Policy(
        name=body.name,
        description=body.description,
        condition=body.condition,
        principal_type=body.principal_type,
        principal_id=body.principal_id,
        action_tool=body.action_tool,
        resource_system=body.resource_system,
        effect=body.effect,
        severity=body.severity,
        compliance_frameworks=body.compliance_frameworks,
        active=True,
        priority=body.priority,
        library=body.library,
        category=body.category,
    )
    policy.id = uuid.uuid4()
    # Compile here so the /intercept hot path never recompiles from columns.
    policy.cedar_text = compile_policy(policy)
    db.add(policy)
    await db.flush()
    invalidate_policy_set_cache()
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
    effective_condition = updated.get("condition", policy.condition)
    errors = validate_condition(effective_condition)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))
    before = {k: getattr(policy, k) for k in updated}
    for field, value in updated.items():
        setattr(policy, field, value)
    # Recompile: any scope or condition edit changes the Cedar source.
    policy.cedar_text = compile_policy(policy)
    await db.flush()
    invalidate_policy_set_cache()
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
    invalidate_policy_set_cache()
