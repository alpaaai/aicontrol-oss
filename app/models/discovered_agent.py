"""DiscoveredAgent — a candidate agent surfaced by passive cloud-API
polling (WS-G, paid tier), not yet promoted to a real registered Agent.
Lives in the community tree (like app/models/mcp_server.py) so the schema
is consistent across editions; the discovery adapters and router that
populate/act on it are enterprise-only.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates
from sqlalchemy.sql import func
from sqlalchemy import TIMESTAMP

from app.models.database import Base


class DiscoveredAgent(Base):
    __tablename__ = "discovered_agents"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_discovered_agents_source_external_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="new")
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    promoted_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    discovered_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, server_default=func.now())

    @validates("confidence")
    def _validate_confidence(self, _key: str, value: str) -> str:
        allowed = {"high", "low"}
        if value not in allowed:
            raise ValueError(f"confidence must be one of {allowed}, got {value!r}")
        return value

    @validates("status")
    def _validate_status(self, _key: str, value: str) -> str:
        allowed = {"new", "promoted", "dismissed"}
        if value not in allowed:
            raise ValueError(f"status must be one of {allowed}, got {value!r}")
        return value
