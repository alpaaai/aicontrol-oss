"""Tests for AWSDiscoveryAdapter (WS-G) -- mocks boto3 clients directly,
no real AWS credentials needed or used."""
from unittest.mock import MagicMock, patch

import pytest


def _paginator_returning(pages):
    paginator = MagicMock()
    paginator.paginate.return_value = pages
    return paginator


@pytest.mark.asyncio
async def test_discover_returns_bedrock_agents_as_high_confidence():
    from enterprise.app.services.discovery.aws_adapter import AWSDiscoveryAdapter

    mock_bedrock = MagicMock()
    mock_bedrock.get_paginator.return_value = _paginator_returning([
        {"agentSummaries": [{"agentId": "AGENT1", "agentName": "claims-bot", "agentStatus": "PREPARED"}]}
    ])
    mock_lambda = MagicMock()
    mock_lambda.get_paginator.return_value = _paginator_returning([{"Functions": []}])

    def _fake_client(service_name, **kwargs):
        return {"bedrock-agent": mock_bedrock, "lambda": mock_lambda}[service_name]

    with patch("enterprise.app.services.discovery.aws_adapter.boto3.client", side_effect=_fake_client):
        adapter = AWSDiscoveryAdapter()
        result = await adapter.discover()

    assert len(result) == 1
    assert result[0].source == "aws_bedrock"
    assert result[0].external_id == "AGENT1"
    assert result[0].confidence == "high"


@pytest.mark.asyncio
async def test_discover_flags_lambda_functions_matching_pattern_as_low_confidence():
    from enterprise.app.services.discovery.aws_adapter import AWSDiscoveryAdapter

    mock_bedrock = MagicMock()
    mock_bedrock.get_paginator.return_value = _paginator_returning([{"agentSummaries": []}])
    mock_lambda = MagicMock()
    mock_lambda.get_paginator.return_value = _paginator_returning([{"Functions": [
        {"FunctionName": "customer-support-agent-prod", "FunctionArn": "arn:aws:lambda:us-east-1:1:function:customer-support-agent-prod"},
        {"FunctionName": "unrelated-utility-fn", "FunctionArn": "arn:aws:lambda:us-east-1:1:function:unrelated-utility-fn"},
    ]}])

    def _fake_client(service_name, **kwargs):
        return {"bedrock-agent": mock_bedrock, "lambda": mock_lambda}[service_name]

    with patch("enterprise.app.services.discovery.aws_adapter.boto3.client", side_effect=_fake_client):
        adapter = AWSDiscoveryAdapter()
        result = await adapter.discover()

    assert len(result) == 1
    assert result[0].source == "aws_lambda_heuristic"
    assert result[0].name == "customer-support-agent-prod"
    assert result[0].confidence == "low"


@pytest.mark.asyncio
async def test_discover_never_raises_on_credential_error():
    from enterprise.app.services.discovery.aws_adapter import AWSDiscoveryAdapter
    from botocore.exceptions import NoCredentialsError

    with patch("enterprise.app.services.discovery.aws_adapter.boto3.client", side_effect=NoCredentialsError()):
        adapter = AWSDiscoveryAdapter()
        result = await adapter.discover()

    assert result == []
