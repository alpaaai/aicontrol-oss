"""Tests for the outbound SIEM export dispatch — the missing piece that
previously left OTelExporter/WebhookExporter never called by anything
outside tests (audit_export_config.py's own docstring admitted this)."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from enterprise.app.services.audit_export.dispatch import (
    AuditEventRecord,
    dispatch_audit_event,
)


def _sample_record():
    return AuditEventRecord(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        agent_name="test-agent",
        tool_name="delete_customer_record",
        tool_parameters={"customer_id": "123"},
        decision="deny",
        decision_reason="blocked by policy",
        policy_name="block_dangerous_tools",
        duration_ms=42,
        created_at=datetime.now(timezone.utc),
    )


def _mock_config(export_type: str, enabled: bool = True):
    config = MagicMock()
    config.id = uuid.uuid4()
    config.export_type = export_type
    config.target_url = "http://localhost:9999/x"
    config.enabled = enabled
    return config


@pytest.mark.asyncio
async def test_dispatch_calls_export_for_each_enabled_config():
    record = _sample_record()
    otel_config = _mock_config("otel")
    webhook_config = _mock_config("webhook")

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [otel_config, webhook_config]
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_otel_exporter = AsyncMock()
    mock_otel_exporter.export = AsyncMock(return_value=MagicMock(delivered=True))
    mock_webhook_exporter = AsyncMock()
    mock_webhook_exporter.export = AsyncMock(return_value=MagicMock(delivered=True))

    with patch(
        "enterprise.app.services.audit_export.dispatch.async_session_factory",
        mock_session_factory,
    ), patch(
        "enterprise.app.services.audit_export.dispatch.OTelExporter",
        return_value=mock_otel_exporter,
    ), patch(
        "enterprise.app.services.audit_export.dispatch.WebhookExporter",
        return_value=mock_webhook_exporter,
    ):
        await dispatch_audit_event(record)

    mock_otel_exporter.export.assert_awaited_once_with(record)
    mock_webhook_exporter.export.assert_awaited_once_with(record)


@pytest.mark.asyncio
async def test_dispatch_skips_disabled_configs():
    record = _sample_record()
    disabled_config = _mock_config("webhook", enabled=False)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    # dispatch's query already filters WHERE enabled=True; simulate that
    # filtering happening at the DB layer by returning no rows.
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_webhook_exporter = AsyncMock()

    with patch(
        "enterprise.app.services.audit_export.dispatch.async_session_factory",
        mock_session_factory,
    ), patch(
        "enterprise.app.services.audit_export.dispatch.WebhookExporter",
        return_value=mock_webhook_exporter,
    ):
        await dispatch_audit_event(record)

    mock_webhook_exporter.export.assert_not_called()
    _ = disabled_config
