import pytest
from enterprise.app.services.policy_authoring.nl_policy_service import NLPolicyService


@pytest.mark.asyncio
async def test_draft_produces_tool_denylist_condition_for_deletion_request():
    service = NLPolicyService()
    draft = await service.draft("Block any agent from calling delete_customer_record")
    assert draft.rule_type == "tool_denylist"
    assert "delete_customer_record" in draft.rego_condition["blocked_tools"]
    assert draft.requires_admin_approval is True


@pytest.mark.asyncio
async def test_draft_rejects_rule_type_outside_existing_enum(monkeypatch):
    service = NLPolicyService()

    async def _fake(desc):
        return {"rule_type": "semantic_similarity_match", "condition": {}, "confidence_notes": "n/a"}

    monkeypatch.setattr(service, "_raw_llm_propose", _fake)
    draft = await service.draft("Block anything that feels like it's trying to exfiltrate data")
    assert draft.rule_type is None
    assert draft.requires_manual_authoring is True
