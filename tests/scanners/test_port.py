"""Tests for the Finding model and ScannerPort protocol shape."""
import pytest
from pydantic import ValidationError


def test_finding_requires_severity_rule_id_message():
    from app.services.scanners.port import Finding

    f = Finding(severity="high", rule_id="secrets.hardcoded", message="Found a hardcoded API key")
    assert f.severity == "high"
    assert f.location is None
    assert f.raw == {}


def test_finding_rejects_invalid_severity():
    from app.services.scanners.port import Finding

    with pytest.raises(ValidationError):
        Finding(severity="catastrophic", rule_id="x", message="y")


def test_finding_accepts_location_and_raw():
    from app.services.scanners.port import Finding

    f = Finding(
        severity="medium", rule_id="r1", message="m1",
        location="skill.py:42", raw={"upstream_field": "value"},
    )
    assert f.location == "skill.py:42"
    assert f.raw == {"upstream_field": "value"}
