package aicontrol

import future.keywords.every
import future.keywords.if
import future.keywords.in

default decision := "allow"
default reason := "default_allow"

# Helper: compare a single policy value against an actual parameter value.
# Uses glob only when val contains wildcard chars (* or ?); otherwise exact equality.
# The string "null" in a policy matches a JSON null parameter value.
param_value_matches(val, actual) if {
    not contains(val, "*")
    not contains(val, "?")
    actual == val
}

# String "null" in policy condition matches a JSON null actual value
param_value_matches("null", actual) if {
    actual == null
}

param_value_matches(val, actual) if {
    contains(val, "*")
    val != "*"
    glob.match(val, [], actual)
}

param_value_matches(val, actual) if {
    contains(val, "?")
    val != "?"
    glob.match(val, [], actual)
}

# Bare "*" or "?" — exact literal match only
param_value_matches("*", actual) if { actual == "*" }
param_value_matches("?", actual) if { actual == "?" }

# Helper: true when all parameter_match conditions pass (or none specified)
params_match(policy) if {
    not policy.condition.parameter_match
}

params_match(policy) if {
    every key, val in policy.condition.parameter_match {
        param_value_matches(val, input.tool_parameters[key])
    }
}

# Helper: evaluate a single numeric operator
numeric_op_passes("gt", actual, threshold) if { actual > threshold }
numeric_op_passes("gte", actual, threshold) if { actual >= threshold }
numeric_op_passes("lt", actual, threshold) if { actual < threshold }
numeric_op_passes("lte", actual, threshold) if { actual <= threshold }
numeric_op_passes("eq", actual, threshold) if { actual == threshold }

# Helper: true when ALL numeric_conditions in a policy pass (AND logic)
numeric_conditions_match(policy) if {
    every cond in policy.condition.numeric_conditions {
        numeric_op_passes(cond.operator, input.tool_parameters[cond.parameter], cond.value)
    }
}

# ── Compound sub-condition helpers ─────────────────────────────────────────────

# Sub-condition parameter_match passes when none defined or all values match
sub_condition_params_match(sub_cond) if {
    not sub_cond.parameter_match
}

sub_condition_params_match(sub_cond) if {
    every key, val in sub_cond.parameter_match {
        param_value_matches(val, input.tool_parameters[key])
    }
}

# Sub-condition numeric_conditions pass when none defined or all ops pass
sub_condition_numeric_match(sub_cond) if {
    not sub_cond.numeric_conditions
}

sub_condition_numeric_match(sub_cond) if {
    every cond in sub_cond.numeric_conditions {
        numeric_op_passes(cond.operator, input.tool_parameters[cond.parameter], cond.value)
    }
}

# A sub-condition passes when both its parameter_match and numeric_conditions pass
sub_condition_passes(sub_cond) if {
    sub_condition_params_match(sub_cond)
    sub_condition_numeric_match(sub_cond)
}

# Helper: true when ALL sub-conditions in all_of pass
all_of_match(policy) if {
    every sub_cond in policy.condition.all_of {
        sub_condition_passes(sub_cond)
    }
}

# Helper: true when ANY sub-condition in any_of passes
any_of_match(policy) if {
    some sub_cond in policy.condition.any_of
    sub_condition_passes(sub_cond)
}

# Per-policy compound violation check (used in is_compound_violation and violation detail)
policy_compound_violation(policy) if {
    policy.condition.all_of
    all_of_match(policy)
}

policy_compound_violation(policy) if {
    policy.condition.any_of
    any_of_match(policy)
}

# ── Tool name matching (primary name + aliases) ────────────────────────────────

# Helper: true if input.tool_name matches a policy's primary tool or any alias
tool_matches(policy) if {
    input.tool_name in policy.condition.blocked_tools
}

tool_matches(policy) if {
    policy.condition.tool_aliases
    input.tool_name in policy.condition.tool_aliases
}

# ── Primary violation helpers ──────────────────────────────────────────────────

# Helper: true if tool is blacklisted with NO conditions (global tool ban)
is_blacklisted if {
    some policy in input.policies
    policy.rule_type == "tool_denylist"
    policy.action == "deny"
    tool_matches(policy)
    not policy.condition.parameter_match
    not policy.condition.numeric_conditions
    not policy.condition.all_of
    not policy.condition.any_of
    not policy.condition.time_conditions
    not policy.condition.token_budget
}

# Helper: true if tool matches AND parameter condition matches (parameter-level violation)
is_parameter_violation if {
    some policy in input.policies
    policy.rule_type == "tool_denylist"
    policy.action == "deny"
    tool_matches(policy)
    policy.condition.parameter_match
    params_match(policy)
}

# Helper: true if tool matches AND all numeric conditions match
is_numeric_violation if {
    some policy in input.policies
    policy.rule_type == "tool_denylist"
    policy.action == "deny"
    tool_matches(policy)
    policy.condition.numeric_conditions
    numeric_conditions_match(policy)
}

# Helper: true if tool matches AND compound all_of/any_of condition matches
is_compound_violation if {
    some policy in input.policies
    policy.rule_type == "tool_denylist"
    policy.action == "deny"
    tool_matches(policy)
    policy_compound_violation(policy)
}

# Helper: get the first violating parameter key=value string
violation_detail := detail if {
    details := {d |
        some policy in input.policies
        policy.rule_type == "tool_denylist"
        policy.action == "deny"
        tool_matches(policy)
        policy.condition.parameter_match
        params_match(policy)
        some key, val in policy.condition.parameter_match
        d := sprintf("parameter_policy_violation: %s=%v", [key, val])
    }
    count(details) > 0
    detail := min(details)
}

# Helper: get one violating numeric condition as a detail string
numeric_violation_detail := detail if {
    details := {d |
        some policy in input.policies
        policy.rule_type == "tool_denylist"
        policy.action == "deny"
        tool_matches(policy)
        policy.condition.numeric_conditions
        numeric_conditions_match(policy)
        some cond in policy.condition.numeric_conditions
        numeric_op_passes(cond.operator, input.tool_parameters[cond.parameter], cond.value)
        d := sprintf("numeric_policy_violation: %s %s %v", [cond.parameter, cond.operator, cond.value])
    }
    count(details) > 0
    detail := min(details)
}

# ── Temporal condition helpers ─────────────────────────────────────────────────

# Helper: current day of week is in the policy's deny_days list
day_is_denied(policy) if {
    policy.condition.time_conditions.deny_days
    input.current_time.day_of_week in policy.condition.time_conditions.deny_days
}

# Helper: current hour falls within the policy's deny_hours window (inclusive from, exclusive to)
hour_is_denied(policy) if {
    policy.condition.time_conditions.deny_hours
    input.current_time.hour >= policy.condition.time_conditions.deny_hours.from
    input.current_time.hour < policy.condition.time_conditions.deny_hours.to
}

# Per-policy time violation check (day or hour triggers the violation)
policy_time_violation(policy) if { day_is_denied(policy) }
policy_time_violation(policy) if { hour_is_denied(policy) }

# Helper: true if tool matches AND a time condition fires
is_time_violation if {
    some policy in input.policies
    policy.rule_type == "tool_denylist"
    policy.action == "deny"
    tool_matches(policy)
    policy.condition.time_conditions
    policy_time_violation(policy)
}

# Helper: detail string for time violation
time_violation_detail := detail if {
    details := {d |
        some policy in input.policies
        policy.rule_type == "tool_denylist"
        policy.action == "deny"
        tool_matches(policy)
        policy.condition.time_conditions
        policy_time_violation(policy)
        d := sprintf("time_policy_violation: %s", [policy.name])
    }
    count(details) > 0
    detail := min(details)
}

# Helper: get the policy name for the first matching compound violation
compound_violation_detail := detail if {
    details := {d |
        some policy in input.policies
        policy.rule_type == "tool_denylist"
        policy.action == "deny"
        tool_matches(policy)
        policy_compound_violation(policy)
        d := sprintf("compound_policy_violation: %s", [policy.name])
    }
    count(details) > 0
    detail := min(details)
}

# Helper: true if the tool matches a review pattern
needs_review if {
    some policy in input.policies
    policy.rule_type == "tool_pattern"
    policy.action == "review"
    some pattern in policy.condition.tool_name_contains
    contains(input.tool_name, pattern)
}

# Helper: true if tool matches a tool_denylist policy with action=review and numeric_conditions
needs_review_numeric if {
    some policy in input.policies
    policy.rule_type == "tool_denylist"
    policy.action == "review"
    tool_matches(policy)
    policy.condition.numeric_conditions
    numeric_conditions_match(policy)
}

# ── Rate-limit helpers ─────────────────────────────────────────────────────────

# Helper: true if a rate_limit policy's threshold is met for the current tool
rate_limit_policy(policy) if {
    policy.rule_type == "rate_limit"
    input.tool_name in policy.condition.tools
    call_count := input.call_counts[input.tool_name]
    call_count >= policy.condition.rate_limit.max_calls
}

# Helper: true if any rate_limit policy fires a deny
is_rate_exceeded_deny if {
    some policy in input.policies
    rate_limit_policy(policy)
    on_exceed := object.get(policy.condition.rate_limit, "on_exceed", "deny")
    on_exceed == "deny"
}

# Helper: true if any rate_limit policy fires a review
is_rate_exceeded_review if {
    some policy in input.policies
    rate_limit_policy(policy)
    on_exceed := object.get(policy.condition.rate_limit, "on_exceed", "deny")
    on_exceed == "review"
}

# Reason string for rate-limit denial or review
rate_limit_reason := reason if {
    some policy in input.policies
    rate_limit_policy(policy)
    max_calls := policy.condition.rate_limit.max_calls
    window := policy.condition.rate_limit.window
    reason := sprintf(
        "rate_limit_exceeded:%s:%d:%s",
        [input.tool_name, max_calls, window]
    )
}

# ── Token/cost budget helpers ──────────────────────────────────────────────────

# Helper: true if a tool_denylist policy's token_budget threshold is met
token_budget_policy(policy) if {
    policy.condition.token_budget.max_tokens
    tool_matches(policy)
    actual := input.cumulative_tokens[input.tool_name]
    actual >= policy.condition.token_budget.max_tokens
}

token_budget_policy(policy) if {
    policy.condition.token_budget.max_cost_usd
    tool_matches(policy)
    actual := input.cumulative_cost_usd[input.tool_name]
    actual >= policy.condition.token_budget.max_cost_usd
}

is_token_budget_exceeded_deny if {
    some policy in input.policies
    token_budget_policy(policy)
    on_exceed := object.get(policy.condition.token_budget, "on_exceed", "deny")
    on_exceed == "deny"
}

is_token_budget_exceeded_review if {
    some policy in input.policies
    token_budget_policy(policy)
    on_exceed := object.get(policy.condition.token_budget, "on_exceed", "deny")
    on_exceed == "review"
}

token_budget_reason := reason if {
    some policy in input.policies
    token_budget_policy(policy)
    threshold := object.get(policy.condition.token_budget, "max_tokens", object.get(policy.condition.token_budget, "max_cost_usd", 0))
    window := policy.condition.token_budget.window
    reason := sprintf(
        "token_budget_exceeded:%s:%v:%s",
        [input.tool_name, threshold, window]
    )
}

# ── Standalone parameter_match rule_type ──────────────────────────────────────
# Evaluates policies with rule_type == "parameter_match".
# Semantics: OR across all keys — any matching key fires the policy.
# Supports two spec forms per key:
#   {key: {contains_any: [...]}}  — case-insensitive substring match
#   {key: {equals: "value"}}      — exact string match
# Wildcard key "*" checks all parameter values for a contains_any match.

_param_str(v) := sprintf("%v", [v])

standalone_param_matches(policy) if {
    some key, spec in policy.condition.parameter_match
    key != "*"
    spec.contains_any
    actual := input.tool_parameters[key]
    some pattern in spec.contains_any
    contains(lower(_param_str(actual)), lower(pattern))
}

standalone_param_matches(policy) if {
    some key, spec in policy.condition.parameter_match
    key != "*"
    spec.equals
    actual := input.tool_parameters[key]
    _param_str(actual) == spec.equals
}

standalone_param_matches(policy) if {
    spec := policy.condition.parameter_match["*"]
    spec.contains_any
    some pattern in spec.contains_any
    some _, actual in input.tool_parameters
    contains(lower(_param_str(actual)), lower(pattern))
}

is_standalone_param_deny if {
    some policy in input.policies
    policy.rule_type == "parameter_match"
    policy.action == "deny"
    standalone_param_matches(policy)
}

is_standalone_param_review if {
    some policy in input.policies
    policy.rule_type == "parameter_match"
    policy.action == "review"
    standalone_param_matches(policy)
}

# ── Standalone numeric_conditions rule_type ───────────────────────────────────
# Evaluates policies with rule_type == "numeric_conditions".
# Semantics: OR across all fields — any matching field fires the policy.
# Condition format: {numeric_conditions: {field: {op: ">"|">="|"<"|"<="|"==", value: N}}}

_snum_op_passes(">",  actual, threshold) if { actual > threshold }
_snum_op_passes(">=", actual, threshold) if { actual >= threshold }
_snum_op_passes("<",  actual, threshold) if { actual < threshold }
_snum_op_passes("<=", actual, threshold) if { actual <= threshold }
_snum_op_passes("==", actual, threshold) if { actual == threshold }

standalone_numeric_matches(policy) if {
    some field, spec in policy.condition.numeric_conditions
    _snum_op_passes(spec.op, input.tool_parameters[field], spec.value)
}

is_standalone_numeric_deny if {
    some policy in input.policies
    policy.rule_type == "numeric_conditions"
    policy.action == "deny"
    standalone_numeric_matches(policy)
}

is_standalone_numeric_review if {
    some policy in input.policies
    policy.rule_type == "numeric_conditions"
    policy.action == "review"
    standalone_numeric_matches(policy)
}

# Deny: global tool blacklist (highest priority)
decision := "deny" if is_blacklisted
reason := "tool_denylisted" if is_blacklisted

# Deny: rate limit exceeded
decision := "deny" if {
    not is_blacklisted
    is_rate_exceeded_deny
}
reason := rate_limit_reason if {
    not is_blacklisted
    is_rate_exceeded_deny
}

# Deny: token/cost budget exceeded
decision := "deny" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    is_token_budget_exceeded_deny
}
reason := token_budget_reason if {
    not is_blacklisted
    not is_rate_exceeded_deny
    is_token_budget_exceeded_deny
}

# Deny: parameter-level violation (tool_denylist + parameter_match condition)
decision := "deny" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    is_parameter_violation
}
reason := violation_detail if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    is_parameter_violation
}

# Deny: numeric condition violation (tool_denylist + numeric_conditions)
decision := "deny" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    is_numeric_violation
}
reason := numeric_violation_detail if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    is_numeric_violation
}

# Deny: compound AND/OR violation
decision := "deny" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    is_compound_violation
}
reason := compound_violation_detail if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    is_compound_violation
}

# Deny: temporal condition violation
decision := "deny" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    is_time_violation
}
reason := time_violation_detail if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    is_time_violation
}

# Deny: standalone parameter_match rule_type
decision := "deny" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    is_standalone_param_deny
}
reason := "standalone_parameter_match_deny" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    is_standalone_param_deny
}

# Deny: standalone numeric_conditions rule_type
decision := "deny" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    is_standalone_numeric_deny
}
reason := "standalone_numeric_conditions_deny" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    is_standalone_numeric_deny
}

# Review: rate limit exceeded
decision := "review" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    not is_standalone_numeric_deny
    is_rate_exceeded_review
}
reason := rate_limit_reason if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    not is_standalone_numeric_deny
    is_rate_exceeded_review
}

# Review: token/cost budget exceeded (soft limit)
decision := "review" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    not is_standalone_numeric_deny
    not is_rate_exceeded_review
    is_token_budget_exceeded_review
}
reason := token_budget_reason if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    not is_standalone_numeric_deny
    not is_rate_exceeded_review
    is_token_budget_exceeded_review
}

# Review: tool_pattern match
decision := "review" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    not is_standalone_numeric_deny
    not is_rate_exceeded_review
    not is_token_budget_exceeded_review
    needs_review
}
reason := "requires_human_review" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    not is_standalone_numeric_deny
    not is_rate_exceeded_review
    not is_token_budget_exceeded_review
    needs_review
}

# Review: tool_denylist + numeric_conditions with action=review
decision := "review" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    not is_standalone_numeric_deny
    not is_rate_exceeded_review
    not is_token_budget_exceeded_review
    not needs_review
    needs_review_numeric
}
reason := "requires_human_review" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    not is_standalone_numeric_deny
    not is_rate_exceeded_review
    not is_token_budget_exceeded_review
    not needs_review
    needs_review_numeric
}

# Review: standalone parameter_match rule_type with action=review
decision := "review" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    not is_standalone_numeric_deny
    not is_rate_exceeded_review
    not is_token_budget_exceeded_review
    not needs_review
    not needs_review_numeric
    is_standalone_param_review
}
reason := "requires_human_review" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    not is_standalone_numeric_deny
    not is_rate_exceeded_review
    not is_token_budget_exceeded_review
    not needs_review
    not needs_review_numeric
    is_standalone_param_review
}

# Review: standalone numeric_conditions rule_type with action=review
decision := "review" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    not is_standalone_numeric_deny
    not is_rate_exceeded_review
    not is_token_budget_exceeded_review
    not needs_review
    not needs_review_numeric
    not is_standalone_param_review
    is_standalone_numeric_review
}
reason := "requires_human_review" if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    not is_standalone_numeric_deny
    not is_rate_exceeded_review
    not is_token_budget_exceeded_review
    not needs_review
    not needs_review_numeric
    not is_standalone_param_review
    is_standalone_numeric_review
}

# ── Fired policy attribution ───────────────────────────────────────────────────
# OPA returns which policy fired so Python never reverse-engineers it from the
# reason string. fired_policy_id="" on allow or when no policy matches.

default fired_policy_id := ""
default fired_policy_name := ""

# Helper: matches either review path (tool_pattern or tool_denylist+numeric)
_review_policy_fires(p) if {
    p.rule_type == "tool_pattern"
    p.action == "review"
    some pat in p.condition.tool_name_contains
    contains(input.tool_name, pat)
}

_review_policy_fires(p) if {
    p.rule_type == "tool_denylist"
    p.action == "review"
    tool_matches(p)
    p.condition.numeric_conditions
    numeric_conditions_match(p)
}

# 1. Blacklist deny
fired_policy_id := min(ids) if {
    is_blacklisted
    ids := {p.id | some p in input.policies; p.rule_type == "tool_denylist"; p.action == "deny"; tool_matches(p); not p.condition.parameter_match; not p.condition.numeric_conditions; not p.condition.all_of; not p.condition.any_of; not p.condition.time_conditions; not p.condition.token_budget}
    count(ids) > 0
}

# 2. Rate-limit deny
fired_policy_id := min(ids) if {
    not is_blacklisted
    is_rate_exceeded_deny
    ids := {p.id | some p in input.policies; rate_limit_policy(p); object.get(p.condition.rate_limit, "on_exceed", "deny") == "deny"}
    count(ids) > 0
}

# 3. Token/cost budget deny
fired_policy_id := min(ids) if {
    not is_blacklisted
    not is_rate_exceeded_deny
    is_token_budget_exceeded_deny
    ids := {p.id | some p in input.policies; token_budget_policy(p); object.get(p.condition.token_budget, "on_exceed", "deny") == "deny"}
    count(ids) > 0
}

# 4. Parameter violation deny
fired_policy_id := min(ids) if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    is_parameter_violation
    ids := {p.id | some p in input.policies; p.rule_type == "tool_denylist"; p.action == "deny"; tool_matches(p); p.condition.parameter_match; params_match(p)}
    count(ids) > 0
}

# 5. Numeric violation deny
fired_policy_id := min(ids) if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    is_numeric_violation
    ids := {p.id | some p in input.policies; p.rule_type == "tool_denylist"; p.action == "deny"; tool_matches(p); p.condition.numeric_conditions; numeric_conditions_match(p)}
    count(ids) > 0
}

# 6. Compound violation deny
fired_policy_id := min(ids) if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    is_compound_violation
    ids := {p.id | some p in input.policies; p.rule_type == "tool_denylist"; p.action == "deny"; tool_matches(p); policy_compound_violation(p)}
    count(ids) > 0
}

# 7. Time violation deny
fired_policy_id := min(ids) if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    is_time_violation
    ids := {p.id | some p in input.policies; p.rule_type == "tool_denylist"; p.action == "deny"; tool_matches(p); p.condition.time_conditions; policy_time_violation(p)}
    count(ids) > 0
}

# 8. Rate-limit review
fired_policy_id := min(ids) if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    is_rate_exceeded_review
    ids := {p.id | some p in input.policies; rate_limit_policy(p); object.get(p.condition.rate_limit, "on_exceed", "deny") == "review"}
    count(ids) > 0
}

# 9. Token/cost budget review
fired_policy_id := min(ids) if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_rate_exceeded_review
    is_token_budget_exceeded_review
    ids := {p.id | some p in input.policies; token_budget_policy(p); object.get(p.condition.token_budget, "on_exceed", "deny") == "review"}
    count(ids) > 0
}

# 10. Pattern review or numeric-condition review
fired_policy_id := min(ids) if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_rate_exceeded_review
    not is_token_budget_exceeded_review
    ids := {p.id | some p in input.policies; _review_policy_fires(p)}
    count(ids) > 0
}

# 11. Standalone parameter_match deny
fired_policy_id := min(ids) if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    is_standalone_param_deny
    ids := {p.id |
        some p in input.policies
        p.rule_type == "parameter_match"
        p.action == "deny"
        standalone_param_matches(p)
    }
    count(ids) > 0
}

# 12. Standalone numeric_conditions deny
fired_policy_id := min(ids) if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    is_standalone_numeric_deny
    ids := {p.id |
        some p in input.policies
        p.rule_type == "numeric_conditions"
        p.action == "deny"
        standalone_numeric_matches(p)
    }
    count(ids) > 0
}

# 13. Standalone parameter_match review
fired_policy_id := min(ids) if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    not is_standalone_numeric_deny
    not is_rate_exceeded_review
    not is_token_budget_exceeded_review
    not needs_review
    not needs_review_numeric
    is_standalone_param_review
    ids := {p.id |
        some p in input.policies
        p.rule_type == "parameter_match"
        p.action == "review"
        standalone_param_matches(p)
    }
    count(ids) > 0
}

# 14. Standalone numeric_conditions review
fired_policy_id := min(ids) if {
    not is_blacklisted
    not is_rate_exceeded_deny
    not is_token_budget_exceeded_deny
    not is_parameter_violation
    not is_numeric_violation
    not is_compound_violation
    not is_time_violation
    not is_standalone_param_deny
    not is_standalone_numeric_deny
    not is_rate_exceeded_review
    not is_token_budget_exceeded_review
    not needs_review
    not needs_review_numeric
    not is_standalone_param_review
    is_standalone_numeric_review
    ids := {p.id |
        some p in input.policies
        p.rule_type == "numeric_conditions"
        p.action == "review"
        standalone_numeric_matches(p)
    }
    count(ids) > 0
}

# Derive name from id — the firing policy is always present in input.policies
fired_policy_name := name if {
    fired_policy_id != ""
    some p in input.policies
    p.id == fired_policy_id
    name := p.name
}
