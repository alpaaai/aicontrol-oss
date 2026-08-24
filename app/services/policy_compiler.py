"""Compile a Policy row into Cedar source.

There is no rule_type dispatch: the presence of a key in `condition` is the
dispatch. Every policy becomes an annotated `forbid`; the catch-all `permit`
is supplied by cedar_client, not by any individual policy.
"""
import json
import re
from typing import Any

from app.models.schemas import Policy

# Cedar numbers are 64-bit integers -- there is no float type, and a float in
# either the policy or the request context makes Cedar reject the whole request
# ("failed to parse schema from request"). Both sides are therefore scaled by
# this factor and compared as integers, which preserves the 6 decimal places the
# cost_usd column already stores. cedar_client applies the same scale to the
# context; the two must never diverge.
NUMERIC_SCALE = 1_000_000

_NUMERIC_OPS = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "eq": "=="}
# The policy library spells operators as symbols; accept both spellings.
_NUMERIC_OPS.update({symbol: symbol for symbol in set(_NUMERIC_OPS.values())})

# base.rego allowed parameter_match on the wildcard key "*", meaning "any
# parameter value contains this". Cedar cannot iterate the context's keys, so
# /intercept flattens every parameter value into one searchable string under
# this name and the wildcard compiles to a match against it.
ALL_PARAMS_FIELD = "all_params_text"

# The modern condition vocabulary a human-facing draft may name -- deliberately
# narrower than everything compile_condition accepts, since tool_name_in,
# blocked_tools, tool_aliases, tools and budget are base.rego compatibility
# spellings kept only so pre-existing conditions keep compiling.
SUPPORTED_CONDITION_KEYS = frozenset({
    "tool_name_contains", "parameter_match", "numeric_conditions",
    "rate_limit", "token_budget", "time_conditions", "all_of", "any_of",
})


def supported_condition_keys() -> frozenset[str]:
    """The single source of truth for what a condition may contain. The NL
    service derives its accepted set from this rather than restating it --
    two hand-maintained lists is how they drift apart."""
    return SUPPORTED_CONDITION_KEYS


def _guard(expr: str) -> str:
    """Prefix every context attribute this expression reads with a `has` check.

    Cedar raises an evaluation error when an expression reads an attribute the
    request's context does not carry, and an errored evaluation comes back as
    Deny -- so a policy about `applicant_id` would break every call that has no
    applicant_id at all. Rego treated a missing key as simply undefined (no
    match), and `context has x && ...` restores exactly that behaviour.
    """
    attrs = sorted(set(re.findall(r"context\.([A-Za-z_][A-Za-z0-9_]*)", expr)))
    if not attrs:
        return expr
    guards = " && ".join(f"context has {a}" for a in attrs)
    return f"{guards} && ({expr})"


def _literal(value: Any) -> str:
    """Render a Python value as a Cedar literal."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(round(value * NUMERIC_SCALE))
    return json.dumps(str(value))


def _tool_name_contains(patterns: list[str]) -> str:
    return " || ".join(f'context.tool_name like "*{p}*"' for p in patterns)


def _tool_name_in(names: list[str]) -> str:
    """Exact tool-name alternation.

    base.rego's `blocked_tools` and `tool_aliases` are exact matches, not
    substring matches. Converting a multi-tool denylist to tool_name_contains
    would silently broaden it -- blocking `delete_database` would also block
    `delete_database_v2`. This key preserves the original semantics; use
    tool_name_contains only where the source policy really was a pattern.
    """
    return " || ".join(f"context.tool_name == {_literal(n)}" for n in names)


def _parameter_match(pairs: dict[str, Any]) -> str:
    """Match call parameters, mirroring base.rego's param_value_matches.

    Rego globs only when the value contains `*` or `?` AND is not bare `*`/`?`;
    a bare wildcard is an exact literal match. Cedar's `like` uses the same `*`
    wildcard syntax, so a glob translates directly -- but a bare `*` must stay
    an equality test or it would match every value instead of the literal.
    """
    parts = []
    for key, value in pairs.items():
        if key == "*":
            key = ALL_PARAMS_FIELD
        if isinstance(value, dict):
            if "contains_any" in value:
                alts = " || ".join(
                    f'context.{key} like "*{n}*"' for n in value["contains_any"]
                )
                parts.append(f"({alts})")
                continue
            if "equals" in value:
                parts.append(f"context.{key} == {_literal(value['equals'])}")
                continue
            raise ValueError(f"unsupported parameter_match form for {key!r}: {value!r}")
        if isinstance(value, str) and value not in ("*", "?") and ("*" in value or "?" in value):
            parts.append(f"context.{key} like {_literal(value)}")
        else:
            parts.append(f"context.{key} == {_literal(value)}")
    return " && ".join(parts)


def _numeric_conditions(fields: Any) -> str:
    # Two shapes exist in the seed data and in customer conditions:
    #   {"amount": {"gt": 5}}                       -- the compact form
    #   [{"parameter": "amount", "operator": "gt", "value": 5}]  -- base.rego's
    # Normalise the list form to the compact one.
    if isinstance(fields, list):
        collapsed: dict[str, dict[str, Any]] = {}
        for entry in fields:
            collapsed.setdefault(entry["parameter"], {})[entry["operator"]] = entry["value"]
        fields = collapsed
    parts = []
    for field, ops in fields.items():
        # Two spellings exist in the seed data: {"gt": N} and the longer
        # {"op": "gt", "value": N} used by the policy library.
        if "op" in ops and "value" in ops:
            ops = {ops["op"]: ops["value"]}
        for op, value in ops.items():
            symbol = _NUMERIC_OPS.get(op)
            if symbol is None:
                raise ValueError(f"unsupported numeric operator: {op!r}")
            parts.append(f"context.{field} {symbol} {_literal(value)}")
    return " && ".join(parts)


def _rate_limit(spec: dict[str, Any]) -> str:
    # Python counts (rate_limit_service); Cedar only compares the number it is handed.
    return f"context.call_count >= {_literal(int(spec['max_calls']))}"


def _token_budget(spec: dict[str, Any]) -> str:
    parts = []
    if "max_tokens" in spec:
        parts.append(f"context.cumulative_tokens > {_literal(int(spec['max_tokens']))}")
    if "max_cost_usd" in spec:
        parts.append(f"context.cumulative_cost_usd > {_literal(spec['max_cost_usd'])}")
    return " || ".join(parts)


def _budget(spec: dict[str, Any]) -> str:
    """Aggregate spend cap. scope="agent" reads the agent-wide running totals,
    anything else reads the org-wide ones. Python supplies the sums
    (token_budget_service); Cedar only compares the number it is handed."""
    prefix = "agent" if spec.get("scope", "agent") == "agent" else "org"
    parts = []
    if "max_tokens" in spec:
        parts.append(f"context.{prefix}_cumulative_tokens > {_literal(int(spec['max_tokens']))}")
    if "max_cost_usd" in spec:
        parts.append(f"context.{prefix}_cumulative_cost_usd > {_literal(spec['max_cost_usd'])}")
    return " || ".join(parts)


def _time_conditions(spec: dict[str, Any]) -> str:
    """Mirror base.rego's policy_time_violation.

    deny_days alone, or deny_hours alone, determines the violation on its own.
    When both are given they are ANDed -- that is deliberate scoping intent
    ("weekends, 9-5"), and base.rego was fixed from OR to AND for exactly this.
    `hours: [start, end]` is the outside-window form used by the C4 table.
    """
    parts = []
    if "deny_days" in spec:
        days = " || ".join(f"context.day_of_week == {_literal(int(d))}" for d in spec["deny_days"])
        parts.append(f"({days})")
    if "deny_hours" in spec:
        window = spec["deny_hours"]
        parts.append(
            f"(context.hour >= {_literal(int(window['from']))} "
            f"&& context.hour < {_literal(int(window['to']))})"
        )
    if "hours" in spec:
        start, end = spec["hours"]
        return f"context.hour < {_literal(int(start))} || context.hour > {_literal(int(end))}"
    return " && ".join(parts)


def compile_condition(condition: dict[str, Any]) -> str:
    """Render a condition dict as a parenthesised Cedar boolean expression.
    Returns "" for an empty condition."""
    if not condition:
        return ""

    # The standalone aggregate-budget policy was written flat, with its fields at
    # the top level of `condition` rather than under a "budget" key. Normalise it
    # so the handler below sees the shape it expects.
    _BUDGET_FIELDS = {"scope", "max_tokens", "max_cost_usd", "on_exceed", "window"}
    if "budget" not in condition and {"max_tokens", "max_cost_usd"} & set(condition):
        budget = {k: v for k, v in condition.items() if k in _BUDGET_FIELDS}
        condition = {k: v for k, v in condition.items() if k not in _BUDGET_FIELDS}
        condition["budget"] = budget

    # blocked_tools, tool_aliases and tools all name exact tools, and base.rego
    # treated aliases as EXTENDING the denylist. Left as separate keys they would
    # be ANDed together by the multi-key join below, requiring tool_name to equal
    # a primary name AND an alias at once -- which nothing can satisfy.
    exact_keys = [k for k in ("blocked_tools", "tool_aliases", "tools") if k in condition]
    if len(exact_keys) > 1 or (exact_keys and "tool_name_in" in condition):
        merged = list(condition.get("tool_name_in", []))
        for key in exact_keys:
            merged.extend(condition[key])
        condition = {k: v for k, v in condition.items() if k not in exact_keys}
        condition["tool_name_in"] = merged

    if "all_of" in condition:
        inner = [compile_condition(c) for c in condition["all_of"]]
        return "(" + " && ".join(i for i in inner if i) + ")"
    if "any_of" in condition:
        inner = [compile_condition(c) for c in condition["any_of"]]
        return "(" + " || ".join(i for i in inner if i) + ")"

    handlers = {
        "tool_name_contains": _tool_name_contains,
        "tool_name_in": _tool_name_in,
        # base.rego's spellings for the same exact-match idea. Kept so a
        # condition written against the old engine still compiles rather than
        # tripping the unknown-key guard below.
        "blocked_tools": _tool_name_in,
        "tool_aliases": _tool_name_in,
        "tools": _tool_name_in,
        "parameter_match": _parameter_match,
        "numeric_conditions": _numeric_conditions,
        "rate_limit": _rate_limit,
        "token_budget": _token_budget,
        "budget": _budget,
        "time_conditions": _time_conditions,
    }
    # Refuse silently-unrenderable conditions. Returning "" for an unknown key
    # would compile the policy to an UNCONDITIONAL forbid -- a policy meant to
    # block one parameter value would block every call in its scope instead.
    # window/on_exceed are Python-side hints (which audit window to count over,
    # what to do on breach). They carry no Cedar expression and are not unknown.
    unknown = set(condition) - set(handlers) - {"all_of", "any_of", "window", "on_exceed"}
    if unknown:
        raise ValueError(
            f"unsupported condition key(s): {sorted(unknown)}. "
            "Add a handler in policy_compiler rather than letting the policy "
            "compile to an unconditional forbid."
        )

    parts = [
        handler(condition[key])
        for key, handler in handlers.items()
        if key in condition
    ]
    parts = [p for p in parts if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return f"({_guard(parts[0])})"
    return "(" + " && ".join(f"({_guard(p)})" for p in parts) + ")"


def compile_policy(policy: Policy) -> str:
    """Render one Policy row as annotated Cedar source, terminated with ';'."""
    if policy.principal_type == "group":
        principal = f'principal in AgentGroup::{json.dumps(policy.principal_id)}'
    elif policy.principal_id:
        principal = f'principal == Agent::{json.dumps(policy.principal_id)}'
    else:
        principal = "principal"

    action = (
        f"action == Action::{json.dumps(policy.action_tool)}"
        if policy.action_tool else "action"
    )
    resource = (
        f"resource == System::{json.dumps(policy.resource_system)}"
        if policy.resource_system else "resource"
    )

    effect = policy.effect or "deny"
    head = (
        f'@id("{policy.id}")\n'
        f'@effect("{effect}")\n'
        f"forbid (\n    {principal},\n    {action},\n    {resource}\n)"
    )
    where = compile_condition(policy.condition or {})
    return f"{head}\nwhen {{ {where} }};" if where else f"{head};"
