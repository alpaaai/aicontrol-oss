"""In-process Cedar evaluation. Replaces the OPA sidecar.

Every AIControl policy compiles to a Cedar `forbid` annotated with its id and
its effect ("deny" or "review"), plus one catch-all `permit`. Cedar answers
Allow or Deny; the third AIControl state is recovered from the diagnostics of
that single evaluation:

  Cedar Allow                       -> allow
  Cedar Deny, any reason @deny      -> deny
  Cedar Deny, all reasons @review   -> review

Precedence therefore stays deny > review > allow, matching the hardcoded
ordering the Rego bundle used. See ADR on the three-valued decision.

Deterministic. Never LLM.
"""
import datetime
import decimal
import hashlib
from typing import Any

from cedarpy import Decision, PolicySet, is_authorized

from app.core.logging import get_logger
from app.services.policy_compiler import NUMERIC_SCALE

logger = get_logger("cedar_client")

CATCH_ALL_PERMIT = "permit (principal, action, resource);"


def current_time_context() -> dict[str, int]:
    """Current UTC day-of-week (0=Mon..6=Sun) and hour, for time_conditions.

    Cedar is no more temporal than Rego was (correction C3): Python supplies
    the numbers, the engine only compares them.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    return {"day_of_week": now.weekday(), "hour": now.hour}

# Pre-parsing the policy set is what keeps evaluation inside the decision
# budget; parsing a 50-policy string on every call is the slow path. Keyed by
# a hash of the policy source, so an edited policy yields a new key.
_policy_set_cache: dict[str, PolicySet] = {}


def invalidate_policy_set_cache() -> None:
    """Drop every cached PolicySet. Called on any policy write."""
    _policy_set_cache.clear()


def _coerce_context(context: dict[str, Any]) -> dict[str, Any]:
    """Turn numeric-looking strings into numbers before evaluation.

    Cedar is strictly typed: `context.amount > 500` against the string "550" does
    not match, so an agent that sends its parameters as strings would slip past
    every numeric policy -- a silent fail-open. Rego had the mirror of this bug
    (string > number cross-type ordering made any string "win"). Coercing here
    closes it for both directions.
    """
    coerced: dict[str, Any] = {}
    for key, value in context.items():
        # cost_usd columns are Numeric(10,6), so SQLAlchemy hands back Decimal,
        # which Cedar cannot serialise -- the whole request is then rejected with
        # "failed to parse schema from request" and every call fails closed.
        if isinstance(value, decimal.Decimal):
            coerced[key] = float(value)
            continue
        if isinstance(value, (dict, list)):
            # Cedar context values are scalars; a nested tool parameter would
            # break the request the same way. Render it as text so a
            # tool_name_contains/parameter_match style check can still see it.
            coerced[key] = str(value)
            continue
        if isinstance(value, bool):
            coerced[key] = value
            continue
        if isinstance(value, str):
            number = None
            try:
                number = int(value)
            except ValueError:
                try:
                    number = float(value)
                except ValueError:
                    number = None
            if number is not None:
                coerced[key] = round(number * NUMERIC_SCALE)
                continue
        if isinstance(value, (int, float)):
            # Scaled to integers to match the compiled thresholds -- Cedar has no
            # float type and rejects the entire request if it sees one.
            coerced[key] = round(value * NUMERIC_SCALE)
            continue
        coerced[key] = value
    return coerced


def _entities(agent_name: str, agent_groups: list[str], system: str) -> list[dict]:
    """Build the Cedar entity list. Group membership is expressed as parents
    on the Agent entity, which is what makes `principal in AgentGroup::"x"`
    match without duplicating a policy per sub-agent."""
    parents = [
        {"__entity": {"type": "AgentGroup", "id": g}} for g in agent_groups
    ]
    entities: list[dict] = [
        {
            "uid": {"__entity": {"type": "Agent", "id": agent_name}},
            "attrs": {},
            "parents": parents,
        },
        {
            "uid": {"__entity": {"type": "System", "id": system}},
            "attrs": {},
            "parents": [],
        },
    ]
    for g in agent_groups:
        entities.append(
            {"uid": {"__entity": {"type": "AgentGroup", "id": g}}, "attrs": {}, "parents": []}
        )
    return entities


def _get_policy_set(policies: list[dict]) -> tuple[PolicySet, str]:
    source = "\n\n".join(
        p["cedar_text"] for p in policies if p.get("cedar_text")
    )
    source = f"{source}\n\n{CATCH_ALL_PERMIT}" if source else CATCH_ALL_PERMIT
    key = hashlib.sha256(source.encode()).hexdigest()
    cached = _policy_set_cache.get(key)
    if cached is None:
        cached = PolicySet.from_str(source)
        _policy_set_cache[key] = cached
    return cached, key


async def evaluate(
    *,
    agent_name: str,
    agent_groups: list[str],
    tool_name: str,
    system: str,
    context: dict[str, Any],
    policies: list[dict],
) -> dict[str, Any]:
    """Evaluate one tool call. Returns the same shape the OPA client returned:
    {"decision", "reason", "fired_policy_id", "fired_policy_name"}."""
    by_id = {str(p["id"]): p for p in policies}

    try:
        policy_set, _ = _get_policy_set(policies)
        result = is_authorized(
            {
                "principal": f'Agent::"{agent_name}"',
                "action": f'Action::"{tool_name}"',
                "resource": f'System::"{system}"',
                "context": _coerce_context(context),
            },
            policy_set,
            _entities(agent_name, agent_groups, system),
        )
    except Exception as exc:  # fail closed — a broken bundle must never fail open
        logger.error("cedar_evaluation_failed", error=str(exc), agent_name=agent_name)
        return {
            "decision": "deny",
            "reason": f"evaluation_error:{type(exc).__name__}",
            "fired_policy_id": None,
            "fired_policy_name": None,
        }

    if result.decision == Decision.Allow:
        return {
            "decision": "allow",
            "reason": "no_matching_policy",
            "fired_policy_id": None,
            "fired_policy_name": None,
        }

    # diagnostics.reasons holds parser-generated ids ("policy1"), not policy uuids.
    # id_annotations_by_reason maps each to the literal @id value -- a bare string,
    # not a dict of annotations -- so @effect is unreadable here and the effect is
    # resolved from `by_id`, the policy map this client already holds. See the D13
    # amendment in the master plan.
    # A Cedar evaluation error surfaces as Deny with errors and NO reasons.
    # Falling through to the review branch below would turn an engine fault into
    # a human-review request; it must fail closed like every other error path.
    errors = list(result.diagnostics.errors or [])
    if errors and not result.diagnostics.reasons:
        logger.error("cedar_evaluation_error", errors=errors[:3], agent_name=agent_name,
                     tool_name=tool_name, context_types={k: type(v).__name__ for k, v in context.items()})
        return {
            "decision": "deny",
            "reason": "evaluation_error:cedar_diagnostics",
            "fired_policy_id": None,
            "fired_policy_name": None,
        }

    annotations = result.diagnostics.id_annotations_by_reason
    matched_ids = [
        annotations.get(str(r), str(r)) for r in result.diagnostics.reasons
    ]

    deny_ids = [
        pid for pid in matched_ids
        if (by_id.get(pid) or {}).get("effect", "deny") == "deny"
    ]
    winning_id = deny_ids[0] if deny_ids else (matched_ids[0] if matched_ids else None)
    decision = "deny" if deny_ids else "review"

    policy = by_id.get(winning_id) if winning_id else None
    return {
        "decision": decision,
        "reason": f"policy_matched:{policy['name']}" if policy else "policy_matched",
        "fired_policy_id": winning_id,
        "fired_policy_name": policy["name"] if policy else None,
    }
