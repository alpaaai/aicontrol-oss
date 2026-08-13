"""Tests for the CloudDiscoveryPort contract (WS-G) -- mirrors
app/services/scanners/port.py's ScannerPort pattern exactly."""
def test_discovered_agent_candidate_rejects_bad_confidence():
    from enterprise.app.services.discovery.port import DiscoveredAgentCandidate
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        DiscoveredAgentCandidate(source="aws_bedrock", external_id="x", name="y", confidence="medium")


def test_discovered_agent_candidate_accepts_valid_confidence():
    from enterprise.app.services.discovery.port import DiscoveredAgentCandidate

    candidate = DiscoveredAgentCandidate(source="aws_bedrock", external_id="x", name="y", confidence="high")
    assert candidate.confidence == "high"
    assert candidate.raw == {}
