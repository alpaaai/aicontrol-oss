"""target_url must be validated at config-creation time to close an SSRF
gap: previously any string was accepted and later passed unguarded to
httpx.post() by WebhookExporter, including loopback/link-local/private-IP
literals (e.g. http://169.254.169.254/ -- cloud metadata endpoints)."""
import pytest


@pytest.mark.parametrize(
    "target_url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8001/",
        "http://localhost/",
        "http://10.0.0.5/",
        "http://172.16.0.5/",
        "http://192.168.1.5/",
        "http://[::1]/",
        "ftp://collector.internal/",
        "not-a-url",
    ],
)
def test_rejects_unsafe_target_urls(target_url):
    from app.models.audit_export_config import AuditExportConfig
    import uuid

    with pytest.raises(ValueError):
        AuditExportConfig(id=uuid.uuid4(), export_type="webhook", target_url=target_url)


@pytest.mark.parametrize(
    "target_url",
    [
        "http://collector.internal/webhook",
        "https://otel-collector.customer.example.com:4318",
    ],
)
def test_accepts_safe_target_urls(target_url):
    from app.models.audit_export_config import AuditExportConfig
    import uuid

    config = AuditExportConfig(id=uuid.uuid4(), export_type="webhook", target_url=target_url)
    assert config.target_url == target_url
