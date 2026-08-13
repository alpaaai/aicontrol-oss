import uuid
from datetime import datetime, timezone

import pytest

from app.models.schemas import AuditEvent


@pytest.fixture
def sample_audit_event():
    return AuditEvent(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        sequence_number=1,
        agent_id=uuid.uuid4(),
        agent_name="test-agent",
        tool_name="delete_customer_record",
        tool_parameters={"customer_id": "123"},
        decision="deny",
        decision_reason="blocked by policy",
        policy_name="block_dangerous_tools",
        duration_ms=42,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_export_formats_audit_event_as_flat_json(sample_audit_event):
    from enterprise.app.services.audit_export.webhook_exporter import WebhookExporter

    exporter = WebhookExporter(webhook_url="http://localhost:9999/webhook")
    record = exporter.format_record(sample_audit_event)
    assert record["event_id"] == str(sample_audit_event.id)
    assert record["decision"] == sample_audit_event.decision
    assert record["tool_name"] == sample_audit_event.tool_name


@pytest.mark.asyncio
async def test_export_does_not_advance_checkpoint_on_delivery_failure(sample_audit_event, tmp_path):
    from enterprise.app.services.audit_export.webhook_exporter import WebhookExporter

    unreachable_webhook_url = "http://127.0.0.1:1/webhook"
    exporter = WebhookExporter(
        webhook_url=unreachable_webhook_url,
        checkpoint_path=tmp_path / "webhook_export.checkpoint",
    )
    result = await exporter.export(sample_audit_event)
    assert result.delivered is False
    assert exporter.checkpoint_unchanged_since_last_success() is True


@pytest.mark.asyncio
async def test_checkpoint_has_lock_to_guard_concurrent_writes(tmp_path):
    import asyncio
    from enterprise.app.services.audit_export.webhook_exporter import WebhookExporter

    exporter = WebhookExporter(webhook_url="http://example.invalid/webhook", checkpoint_path=tmp_path / "c.checkpoint")
    assert isinstance(exporter._checkpoint_lock, asyncio.Lock)


@pytest.mark.asyncio
async def test_out_of_order_delivery_does_not_regress_checkpoint(monkeypatch, tmp_path):
    from enterprise.app.services.audit_export.webhook_exporter import WebhookExporter

    class _FakeResponse:
        def raise_for_status(self):
            pass

    class _FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return _FakeResponse()

    monkeypatch.setattr("enterprise.app.services.audit_export.webhook_exporter.httpx.AsyncClient", _FakeAsyncClient)

    exporter = WebhookExporter(webhook_url="http://example.invalid/webhook", checkpoint_path=tmp_path / "c.checkpoint")

    older = AuditEvent(
        id=uuid.uuid4(), session_id=uuid.uuid4(), sequence_number=1, agent_id=uuid.uuid4(),
        agent_name="a", tool_name="t", tool_parameters={}, decision="allow",
        decision_reason="x", duration_ms=1, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer = AuditEvent(
        id=uuid.uuid4(), session_id=uuid.uuid4(), sequence_number=2, agent_id=uuid.uuid4(),
        agent_name="a", tool_name="t", tool_parameters={}, decision="allow",
        decision_reason="x", duration_ms=1, created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )

    await exporter.export(newer)
    await exporter.export(older)

    assert str(newer.id) in exporter.checkpoint_path.read_text()
    assert str(older.id) not in exporter.checkpoint_path.read_text()
