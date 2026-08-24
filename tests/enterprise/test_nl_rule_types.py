"""The NL service's accepted set is derived from the compiler, not restated."""
from app.services import policy_compiler
from enterprise.app.services.policy_authoring.nl_policy_service import ACCEPTED_CONDITION_KEYS


def test_accepted_keys_match_the_compiler_exactly():
    compiler_keys = policy_compiler.supported_condition_keys()
    assert ACCEPTED_CONDITION_KEYS == compiler_keys


def test_rule_type_is_gone():
    import inspect
    from enterprise.app.services.policy_authoring import nl_policy_service
    source = inspect.getsource(nl_policy_service)
    assert "rule_type" not in source


def test_unknown_condition_key_requires_manual_authoring():
    from enterprise.app.services.policy_authoring.nl_policy_service import validate_draft
    result = validate_draft({"condition": {"geofence": {"country": "US"}}})
    assert result.status == "requires_manual_authoring"


def test_every_compiler_key_validates_clean():
    from enterprise.app.services.policy_authoring.nl_policy_service import validate_draft
    samples = {
        "tool_name_contains": ["credit"],
        "parameter_match": {"region": "eu"},
        "numeric_conditions": {"amount": {"gt": 1}},
        "rate_limit": {"max_calls": 5},
        "token_budget": {"max_tokens": 100},
        "time_conditions": {"hours": [6, 20]},
        "all_of": [{"numeric_conditions": {"amount": {"gt": 1}}}],
        "any_of": [{"numeric_conditions": {"amount": {"gt": 1}}}],
    }
    for key, value in samples.items():
        result = validate_draft({"condition": {key: value}})
        assert result.status != "requires_manual_authoring", key
