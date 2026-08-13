"""AuditExportConfig — a per-tenant outbound SIEM export target (OTLP
endpoint or webhook URL). Lives in the community tree (like
app/models/mcp_server.py) so the schema is consistent across editions;
the exporters and router that populate/act on it are enterprise-only.
"""
import ipaddress
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, validates
from sqlalchemy.sql import func
from sqlalchemy import TIMESTAMP

from app.models.database import Base

_BLOCKED_HOSTNAMES = {"localhost"}


def validate_target_url(value: str) -> str:
    """Reject obviously-SSRF-prone targets: non-http(s) schemes, and
    loopback/link-local/private-range IP literals or localhost. This is a
    literal check only -- it does not resolve DNS, so a hostname that
    later resolves to a private address at request time isn't caught here.
    """
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"target_url must be http or https, got {value!r}")
    host = parsed.hostname
    if not host:
        raise ValueError(f"target_url must have a host, got {value!r}")
    if host.lower() in _BLOCKED_HOSTNAMES:
        raise ValueError(f"target_url host {host!r} is not allowed")
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return value  # not an IP literal -- allow (DNS-based hosts aren't resolved here)
    if addr.is_loopback or addr.is_link_local or addr.is_private or addr.is_reserved or addr.is_multicast:
        raise ValueError(f"target_url host {host!r} resolves to a disallowed IP range")
    return value


class AuditExportConfig(Base):
    __tablename__ = "audit_export_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    export_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, server_default=func.now())

    @validates("export_type")
    def _validate_export_type(self, _key: str, value: str) -> str:
        allowed = {"otel", "webhook"}
        if value not in allowed:
            raise ValueError(f"export_type must be one of {allowed}, got {value!r}")
        return value

    @validates("target_url")
    def _validate_target_url(self, _key: str, value: str) -> str:
        return validate_target_url(value)
