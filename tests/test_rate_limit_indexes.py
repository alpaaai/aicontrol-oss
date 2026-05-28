"""Tests for P1-2: composite indexes on audit_events for rate-limit COUNT queries."""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session_factory


@pytest.mark.asyncio
async def test_session_tool_index_exists():
    async with async_session_factory() as session:
        result = await session.execute(text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'audit_events'
              AND indexname = 'ix_audit_events_session_tool'
        """))
        assert result.scalar_one_or_none() == 'ix_audit_events_session_tool'


@pytest.mark.asyncio
async def test_agent_tool_time_index_exists():
    async with async_session_factory() as session:
        result = await session.execute(text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'audit_events'
              AND indexname = 'ix_audit_events_agent_tool_time'
        """))
        assert result.scalar_one_or_none() == 'ix_audit_events_agent_tool_time'
