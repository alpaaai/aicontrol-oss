"""Live-path regression: the model fences its JSON, json.loads() does not.

The first real (non-mock) run of NLPolicyService failed with
JSONDecodeError: Expecting value: line 1 column 1 (char 0) because Claude
returned the draft wrapped in a ```json ... ``` markdown fence. The mock path
never exercised this -- mock_response is already bare JSON -- so the defect was
invisible until an ANTHROPIC_API_KEY was present.
"""
import pytest

from enterprise.app.services.policy_authoring.nl_policy_service import _parse_llm_json

BARE = '{"rule_type": "tool_denylist", "condition": {"blocked_tools": ["x"]}}'


def test_parses_bare_json():
    assert _parse_llm_json(BARE)["rule_type"] == "tool_denylist"


def test_parses_json_fenced_block():
    raw = f"```json\n{BARE}\n```"
    assert _parse_llm_json(raw)["rule_type"] == "tool_denylist"


def test_parses_unlabelled_fenced_block():
    raw = f"```\n{BARE}\n```"
    assert _parse_llm_json(raw)["rule_type"] == "tool_denylist"


def test_parses_fenced_block_with_surrounding_prose():
    raw = f"Here is the draft:\n\n```json\n{BARE}\n```\n\nLet me know if that works."
    assert _parse_llm_json(raw)["rule_type"] == "tool_denylist"


def test_raises_on_genuinely_unparseable_output():
    with pytest.raises(ValueError):
        _parse_llm_json("I cannot help with that request.")


def test_system_prompt_pins_the_tool_denylist_condition_key():
    """The prompt said 'a dict matching that rule_type's existing condition
    shape' without ever stating the shape, so the model returned {"tools": [...]}
    while every consumer reads condition["blocked_tools"]."""
    from enterprise.app.services.policy_authoring.prompt_builder import SYSTEM_PROMPT

    assert "blocked_tools" in SYSTEM_PROMPT
