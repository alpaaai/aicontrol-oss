import uuid
import pytest

from app.services.session_tracking import RISK_SCORE_DELTA, accumulate_session_risk, ensure_session


@pytest.mark.asyncio
async def test_ensure_session_is_idempotent(db_session):
    from app.models.schemas import Agent, Session

    agent = Agent(id=uuid.uuid4(), name="test-agent-session-1", owner="qa")
    db_session.add(agent)
    await db_session.flush()
    session_id = uuid.uuid4()

    await ensure_session(db_session, session_id, agent.id)
    await ensure_session(db_session, session_id, agent.id)  # must not raise on the second call

    result = await db_session.get(Session, session_id)
    assert result is not None


@pytest.mark.asyncio
async def test_accumulate_session_risk_adds_delta(db_session):
    from app.models.schemas import Agent, Session

    agent = Agent(id=uuid.uuid4(), name="test-agent-session-2", owner="qa")
    db_session.add(agent)
    await db_session.flush()
    session_id = uuid.uuid4()
    await ensure_session(db_session, session_id, agent.id)

    await accumulate_session_risk(db_session, session_id, RISK_SCORE_DELTA["deny"])
    await db_session.flush()
    result = await db_session.get(Session, session_id)
    assert result.risk_score == RISK_SCORE_DELTA["deny"]
