"""GA review finding: a real (non-mock) claude-haiku-4-5 response wraps its
JSON in a ```json code fence despite the system prompt's explicit "no
markdown fences" instruction. json.loads(raw) throws on the fence, and every
real (non-mock) compliance report generation fails 100% reproducibly."""
import json

from enterprise.compliance.service import parse_narratives


def test_parse_narratives_handles_bare_json():
    raw = json.dumps({"soc2": "narrative text"})
    assert parse_narratives(raw) == {"soc2": "narrative text"}


def test_parse_narratives_strips_json_fence():
    raw = "```json\n" + json.dumps({"soc2": "narrative text"}) + "\n```"
    assert parse_narratives(raw) == {"soc2": "narrative text"}


def test_parse_narratives_strips_bare_fence():
    raw = "```\n" + json.dumps({"soc2": "narrative text"}) + "\n```"
    assert parse_narratives(raw) == {"soc2": "narrative text"}


def test_parse_narratives_strips_surrounding_whitespace_around_fence():
    raw = "  \n```json\n" + json.dumps({"eu_ai_act": "x"}) + "\n```  \n"
    assert parse_narratives(raw) == {"eu_ai_act": "x"}
