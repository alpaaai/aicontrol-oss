import pytest
from unittest.mock import patch
from app.services.ai_client import AIClient
from app.services import ai_client as ai_client_module


@pytest.mark.asyncio
async def test_mock_returns_mock_response():
    with patch.object(ai_client_module.settings, "LLM_MOCK_ENABLED", True):
        result = await AIClient.complete(
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100,
            system_prompt="test",
            feature_name="test_feature",
            mock_response="expected output",
        )
    assert result == "expected output"


@pytest.mark.asyncio
async def test_raises_on_zero_max_tokens():
    with pytest.raises(ValueError, match="max_tokens must be positive"):
        await AIClient.complete(
            messages=[],
            max_tokens=0,
            system_prompt="",
            feature_name="test_feature",
        )
