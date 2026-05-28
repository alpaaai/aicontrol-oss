import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import UUID, Boolean, Date, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.database import Base


class ComplianceReport(Base):
    __tablename__ = "compliance_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=func.now())
    date_from: Mapped[datetime] = mapped_column(Date, nullable=False)
    date_to: Mapped[datetime] = mapped_column(Date, nullable=False)
    frameworks: Mapped[list] = mapped_column(ARRAY(String), nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    generated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    report_path: Mapped[str] = mapped_column(Text, nullable=False)
    md_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_model: Mapped[str] = mapped_column(String(100), nullable=False)
    mock_used: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    token_input: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_output: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
