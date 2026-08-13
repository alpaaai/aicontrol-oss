"""AuditExportConfig — a per-tenant outbound SIEM export target (OTLP
endpoint or webhook URL). Lives in the community tree (like
app/models/mcp_server.py) so the schema is consistent across editions;
the exporters and router that populate/act on it are enterprise-only.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, validates
from sqlalchemy.sql import func
from sqlalchemy import TIMESTAMP

from app.models.database import Base


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
