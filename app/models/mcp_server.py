"""MCPServer — a downstream HTTP MCP server registered with the MCP Native
Proxy (WS1, paid tier). This model lives in the community tree (like
app/models/policy_warning.py) so the schema is consistent across editions;
the router and gateway that populate and use it are enterprise-only.

auth_token is stored in plaintext. This is a known limitation carried
forward from the existing pattern (settings.slack_bot_token is also a plain
env var) — encryption-at-rest for per-server credentials is not in scope for
this plan and should be a follow-up if enterprise customers require it.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates
from sqlalchemy.sql import func
from sqlalchemy import TIMESTAMP

from app.models.database import Base


class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    auth_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="none")
    auth_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending_scan")
    approved_tools: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, server_default=func.now())

    @validates("auth_type")
    def _validate_auth_type(self, _key: str, value: str) -> str:
        allowed = {"none", "bearer"}
        if value not in allowed:
            raise ValueError(f"auth_type must be one of {allowed}, got {value!r}")
        return value

    @validates("status")
    def _validate_status(self, _key: str, value: str) -> str:
        allowed = {"pending_scan", "active", "blocked"}
        if value not in allowed:
            raise ValueError(f"status must be one of {allowed}, got {value!r}")
        return value
