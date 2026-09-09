"""MCPServer — a downstream MCP server registered with the AIControl gateway
(app/routers/mcp_gateway.py). Registration is metadata-only: no credential is
ever stored here (Decision 9, plans/2026-09-07-gateway-pivot.md) — whatever
Authorization header a gateway caller presents is forwarded to base_url
unchanged. This supersedes the deleted enterprise/mcp_gateway/'s MCPServer,
which stored a plaintext auth_token on this row; that violates the current
pure-passthrough design and must not be reintroduced."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates
from sqlalchemy.sql import func

from app.models.database import Base


class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending_review")
    approved_tools: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, server_default=func.now())

    @validates("status")
    def _validate_status(self, _key: str, value: str) -> str:
        allowed = {"pending_review", "active", "blocked"}
        if value not in allowed:
            raise ValueError(f"status must be one of {allowed}, got {value!r}")
        return value
