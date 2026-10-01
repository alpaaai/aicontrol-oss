import re
from pathlib import Path

_REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"


def test_stripe_dependency_is_pinned():
    lines = _REQUIREMENTS.read_text().splitlines()
    stripe_lines = [line for line in lines if re.match(r"^stripe\b", line.strip())]
    assert stripe_lines, "stripe dependency missing from requirements.txt"
    assert "==" in stripe_lines[0], f"stripe must be pinned with ==, got: {stripe_lines[0]!r}"
