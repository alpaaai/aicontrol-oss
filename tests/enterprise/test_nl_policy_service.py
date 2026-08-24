import pytest
from enterprise.app.services.policy_authoring.nl_policy_service import NLPolicyService


@pytest.mark.asyncio
async def test_draft_produces_a_tool_name_contains_condition_for_deletion_request(monkeypatch):
    service = NLPolicyService()

    async def _fake(desc):
        return {
            "principal_type": None,
            "principal_id": None,
            "action_tool": None,
            "resource_system": None,
            "effect": "deny",
            "condition": {"tool_name_contains": ["delete_customer_record"]},
            "confidence_notes": "Direct tool-name match, high confidence.",
        }

    monkeypatch.setattr(service, "_raw_llm_propose", _fake)
    result = await service.draft("Block any agent from calling delete_customer_record")
    assert "delete_customer_record" in result["draft"]["condition"]["tool_name_contains"]
    assert result["status"] == "drafted"


@pytest.mark.asyncio
async def test_draft_rejects_a_condition_key_outside_the_accepted_set(monkeypatch):
    service = NLPolicyService()

    async def _fake(desc):
        return {
            "principal_type": None,
            "principal_id": None,
            "action_tool": None,
            "resource_system": None,
            "effect": "deny",
            "condition": {"geofence": {"country": "US"}},
            "confidence_notes": "n/a",
        }

    monkeypatch.setattr(service, "_raw_llm_propose", _fake)
    result = await service.draft("Block anything that feels like it's trying to exfiltrate data")
    assert result["draft"] is None
    assert result["status"] == "requires_manual_authoring"
