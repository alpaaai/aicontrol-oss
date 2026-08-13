"""Tests for the discovered_agents table (WS-G)."""
import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


@pytest.mark.asyncio
async def test_discovered_agents_table_accepts_a_row_and_defaults_to_new():
    from app.models.database import async_session_factory

    row_id = uuid.uuid4()
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO discovered_agents (id, source, external_id, name, confidence)
            VALUES (:id, 'aws_bedrock', 'AGENT123', 'test-discovered-agent', 'high')
        """), {"id": str(row_id)})
        await session.commit()

        result = await session.execute(
            text("SELECT status FROM discovered_agents WHERE id = :id"), {"id": str(row_id)}
        )
        assert result.scalar_one() == "new"

        await session.execute(text("DELETE FROM discovered_agents WHERE id = :id"), {"id": str(row_id)})
        await session.commit()


@pytest.mark.asyncio
async def test_discovered_agents_unique_on_source_and_external_id():
    from app.models.database import async_session_factory

    row_id = uuid.uuid4()
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO discovered_agents (id, source, external_id, name, confidence)
            VALUES (:id, 'aws_bedrock', 'AGENT456', 'dup-test', 'high')
        """), {"id": str(row_id)})
        await session.commit()

        with pytest.raises(IntegrityError):
            await session.execute(text("""
                INSERT INTO discovered_agents (id, source, external_id, name, confidence)
                VALUES (:id2, 'aws_bedrock', 'AGENT456', 'dup-test-again', 'high')
            """), {"id2": str(uuid.uuid4())})
            await session.commit()
        await session.rollback()

        await session.execute(text("DELETE FROM discovered_agents WHERE id = :id"), {"id": str(row_id)})
        await session.commit()
