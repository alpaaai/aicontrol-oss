"""Fixtures for the NL policy authoring tests. mock_llm and mock_llm_geofence
patch NLPolicyService._raw_llm_propose directly so these tests need no LLM
provider key and no live network call -- the fixed replies below are what a
model call to this feature would return for exactly these descriptions."""
import pytest

from enterprise.app.services.policy_authoring.nl_policy_service import NLPolicyService

_PAYMENT_DESCRIPTION = (
    "the claims adjuster must not release a payment over 50000 dollars on guidewire"
)

_RESPONSES = {
    _PAYMENT_DESCRIPTION: {
        "principal_type": "agent",
        "principal_id": "claims-adjuster",
        "action_tool": "release_payment",
        "resource_system": "guidewire",
        "effect": "review",
        "condition": {"numeric_conditions": {"amount": {"gt": 50000}}},
        "confidence_notes": "Direct match on agent, tool, system and threshold.",
    },
    "block bulk claims queries": {
        "principal_type": None,
        "principal_id": None,
        "action_tool": "db_query",
        "resource_system": None,
        "effect": "deny",
        "condition": {"numeric_conditions": {"row_count": {"gt": 100}}},
        "confidence_notes": "Bulk-query pattern, no agent named.",
    },
}

_NO_FIXTURE_RESPONSE = {
    "principal_type": None,
    "principal_id": None,
    "action_tool": None,
    "resource_system": None,
    "effect": "deny",
    "condition": {},
    "confidence_notes": "No mock fixture for this description.",
}

_GEOFENCE_RESPONSE = {
    "principal_type": None,
    "principal_id": None,
    "action_tool": None,
    "resource_system": None,
    "effect": "deny",
    "condition": {"geofence": {"country": "US"}},
    "confidence_notes": "Geofencing is not a supported condition.",
}


@pytest.fixture
def mock_llm(monkeypatch):
    async def _fake(self, description):
        return _RESPONSES.get(description, _NO_FIXTURE_RESPONSE)

    monkeypatch.setattr(NLPolicyService, "_raw_llm_propose", _fake)


@pytest.fixture
def mock_llm_geofence(monkeypatch):
    async def _fake(self, description):
        return _GEOFENCE_RESPONSE

    monkeypatch.setattr(NLPolicyService, "_raw_llm_propose", _fake)
