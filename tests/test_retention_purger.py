"""Tests for app/services/retention_purger.py (plan 3.3 fix -- audit_events
retention was advertised (7-day Community, 30-day Business, 90-day
Enterprise/Trial) but never enforced; the query-layer clamp in
audit_events.py only limited what Community could *see*, not what was
actually stored)."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.license_gate import LicenseInfo
from app.models.schemas import AuditEvent, HITLReview
from app.services.retention_purger import RetentionPurger, purge_expired_audit_events


async def _make_audit_event(session, agent_id, session_id, created_at, sequence_number=1):
    event = AuditEvent(
        id=uuid.uuid4(), session_id=session_id, agent_id=agent_id,
        agent_name="retention-test-agent", tool_name="safe_tool",
        tool_parameters={}, decision="allow", decision_reason="test",
        sequence_number=sequence_number, duration_ms=1, risk_delta=0,
    )
    session.add(event)
    await session.flush()
    await session.execute(
        AuditEvent.__table__.update().where(AuditEvent.id == event.id).values(created_at=created_at)
    )
    return event


@pytest.mark.asyncio
async def test_purge_deletes_events_older_than_community_window():
    from app.models.database import async_session_factory
    from tests.conftest import AGENTS

    agent_id = AGENTS[0]["id"]
    session_id = uuid.uuid4()
    async with async_session_factory() as session:
        from app.models.schemas import Session as SessionModel
        session.add(SessionModel(id=session_id, agent_id=agent_id, status="active"))
        await session.flush()
        old_event = await _make_audit_event(
            session, agent_id, session_id,
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=8),
        )
        recent_event = await _make_audit_event(
            session, agent_id, session_id,
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1),
            sequence_number=2,
        )
        await session.commit()

    try:
        async with async_session_factory() as session:
            # `deleted` is a table-wide count (purge_expired_audit_events has
            # no per-test scoping) -- this dev DB also accumulates demo/other
            # old rows, so asserting an exact count here is flaky depending
            # on what else happens to be stale at run time. The real
            # assertion is the per-row check below.
            deleted = await purge_expired_audit_events(session, "community")
            assert deleted >= 1

        async with async_session_factory() as session:
            remaining = (await session.execute(
                select(AuditEvent.id).where(AuditEvent.id.in_([old_event.id, recent_event.id]))
            )).scalars().all()
            assert remaining == [recent_event.id]
    finally:
        async with async_session_factory() as session:
            await session.execute(
                AuditEvent.__table__.delete().where(AuditEvent.id.in_([old_event.id, recent_event.id]))
            )
            await session.execute(SessionModel.__table__.delete().where(SessionModel.id == session_id))
            await session.commit()


@pytest.mark.asyncio
async def test_purge_deletes_referencing_hitl_review_first():
    """hitl_reviews.audit_event_id has no ON DELETE CASCADE -- deleting
    audit_events first would raise an IntegrityError."""
    from app.models.database import async_session_factory
    from app.models.schemas import Session as SessionModel
    from tests.conftest import AGENTS

    agent_id = AGENTS[0]["id"]
    session_id = uuid.uuid4()
    async with async_session_factory() as session:
        session.add(SessionModel(id=session_id, agent_id=agent_id, status="active"))
        await session.flush()
        old_event = await _make_audit_event(
            session, agent_id, session_id,
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=400),
        )
        review = HITLReview(id=uuid.uuid4(), audit_event_id=old_event.id, session_id=session_id, status="pending")
        session.add(review)
        await session.commit()

    try:
        async with async_session_factory() as session:
            # See the community-window test above re: why this isn't ==1.
            deleted = await purge_expired_audit_events(session, "business")
            assert deleted >= 1

        async with async_session_factory() as session:
            remaining_event = (await session.execute(
                select(AuditEvent.id).where(AuditEvent.id == old_event.id)
            )).scalar_one_or_none()
            assert remaining_event is None
            remaining_review = (await session.execute(
                select(HITLReview.id).where(HITLReview.id == review.id)
            )).scalar_one_or_none()
            assert remaining_review is None
    finally:
        async with async_session_factory() as session:
            await session.execute(AuditEvent.__table__.delete().where(AuditEvent.id == old_event.id))
            await session.execute(HITLReview.__table__.delete().where(HITLReview.id == review.id))
            await session.execute(SessionModel.__table__.delete().where(SessionModel.id == session_id))
            await session.commit()


@pytest.mark.asyncio
async def test_purge_keeps_business_events_within_30_day_window():
    from app.models.database import async_session_factory
    from app.models.schemas import Session as SessionModel
    from tests.conftest import AGENTS

    agent_id = AGENTS[0]["id"]
    session_id = uuid.uuid4()
    async with async_session_factory() as session:
        session.add(SessionModel(id=session_id, agent_id=agent_id, status="active"))
        await session.flush()
        event = await _make_audit_event(
            session, agent_id, session_id,
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10),
        )
        await session.commit()

    try:
        async with async_session_factory() as session:
            # Table-wide call (see community-window test above) -- the real
            # assertion is that THIS event specifically survives, not that
            # nothing else in the shared dev DB was stale enough to purge.
            await purge_expired_audit_events(session, "business")
        async with async_session_factory() as session:
            remaining_event = (await session.execute(
                select(AuditEvent.id).where(AuditEvent.id == event.id)
            )).scalar_one_or_none()
            assert remaining_event == event.id
    finally:
        async with async_session_factory() as session:
            await session.execute(AuditEvent.__table__.delete().where(AuditEvent.id == event.id))
            await session.execute(SessionModel.__table__.delete().where(SessionModel.id == session_id))
            await session.commit()


@pytest.mark.asyncio
async def test_purge_deletes_business_events_over_30_day_window():
    from app.models.database import async_session_factory
    from app.models.schemas import Session as SessionModel
    from tests.conftest import AGENTS

    agent_id = AGENTS[0]["id"]
    session_id = uuid.uuid4()
    async with async_session_factory() as session:
        session.add(SessionModel(id=session_id, agent_id=agent_id, status="active"))
        await session.flush()
        event = await _make_audit_event(
            session, agent_id, session_id,
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=40),
        )
        await session.commit()

    try:
        async with async_session_factory() as session:
            # See community-window test above re: table-wide deleted count.
            deleted = await purge_expired_audit_events(session, "business")
            assert deleted >= 1
        async with async_session_factory() as session:
            remaining_event = (await session.execute(
                select(AuditEvent.id).where(AuditEvent.id == event.id)
            )).scalar_one_or_none()
            assert remaining_event is None
    finally:
        async with async_session_factory() as session:
            await session.execute(AuditEvent.__table__.delete().where(AuditEvent.id == event.id))
            await session.execute(SessionModel.__table__.delete().where(SessionModel.id == session_id))
            await session.commit()


@pytest.mark.asyncio
async def test_purge_keeps_enterprise_events_within_90_day_window():
    from app.models.database import async_session_factory
    from app.models.schemas import Session as SessionModel
    from tests.conftest import AGENTS

    agent_id = AGENTS[0]["id"]
    session_id = uuid.uuid4()
    async with async_session_factory() as session:
        session.add(SessionModel(id=session_id, agent_id=agent_id, status="active"))
        await session.flush()
        event = await _make_audit_event(
            session, agent_id, session_id,
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30),
        )
        await session.commit()

    try:
        async with async_session_factory() as session:
            # See community-window test above re: table-wide deleted count.
            await purge_expired_audit_events(session, "enterprise")
        async with async_session_factory() as session:
            remaining_event = (await session.execute(
                select(AuditEvent.id).where(AuditEvent.id == event.id)
            )).scalar_one_or_none()
            assert remaining_event == event.id
    finally:
        async with async_session_factory() as session:
            await session.execute(AuditEvent.__table__.delete().where(AuditEvent.id == event.id))
            await session.execute(SessionModel.__table__.delete().where(SessionModel.id == session_id))
            await session.commit()


@pytest.mark.asyncio
async def test_purge_deletes_enterprise_events_over_90_day_window():
    from app.models.database import async_session_factory
    from app.models.schemas import Session as SessionModel
    from tests.conftest import AGENTS

    agent_id = AGENTS[0]["id"]
    session_id = uuid.uuid4()
    async with async_session_factory() as session:
        session.add(SessionModel(id=session_id, agent_id=agent_id, status="active"))
        await session.flush()
        event = await _make_audit_event(
            session, agent_id, session_id,
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=100),
        )
        await session.commit()

    try:
        async with async_session_factory() as session:
            # See community-window test above re: table-wide deleted count.
            deleted = await purge_expired_audit_events(session, "enterprise")
            assert deleted >= 1
        async with async_session_factory() as session:
            remaining_event = (await session.execute(
                select(AuditEvent.id).where(AuditEvent.id == event.id)
            )).scalar_one_or_none()
            assert remaining_event is None
    finally:
        async with async_session_factory() as session:
            await session.execute(AuditEvent.__table__.delete().where(AuditEvent.id == event.id))
            await session.execute(SessionModel.__table__.delete().where(SessionModel.id == session_id))
            await session.commit()


@pytest.mark.asyncio
async def test_purge_keeps_trial_events_within_90_day_window():
    """Trial mirrors enterprise's 90-day window (not community's 7-day
    fallback) -- see the RETENTION_DAYS["trial"] key comment."""
    from app.models.database import async_session_factory
    from app.models.schemas import Session as SessionModel
    from tests.conftest import AGENTS

    agent_id = AGENTS[0]["id"]
    session_id = uuid.uuid4()
    async with async_session_factory() as session:
        session.add(SessionModel(id=session_id, agent_id=agent_id, status="active"))
        await session.flush()
        event = await _make_audit_event(
            session, agent_id, session_id,
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30),
        )
        await session.commit()

    try:
        async with async_session_factory() as session:
            # See community-window test above re: table-wide deleted count.
            await purge_expired_audit_events(session, "trial")
        async with async_session_factory() as session:
            remaining_event = (await session.execute(
                select(AuditEvent.id).where(AuditEvent.id == event.id)
            )).scalar_one_or_none()
            assert remaining_event == event.id
    finally:
        async with async_session_factory() as session:
            await session.execute(AuditEvent.__table__.delete().where(AuditEvent.id == event.id))
            await session.execute(SessionModel.__table__.delete().where(SessionModel.id == session_id))
            await session.commit()


@pytest.mark.asyncio
async def test_purge_deletes_trial_events_over_90_day_window():
    from app.models.database import async_session_factory
    from app.models.schemas import Session as SessionModel
    from tests.conftest import AGENTS

    agent_id = AGENTS[0]["id"]
    session_id = uuid.uuid4()
    async with async_session_factory() as session:
        session.add(SessionModel(id=session_id, agent_id=agent_id, status="active"))
        await session.flush()
        event = await _make_audit_event(
            session, agent_id, session_id,
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=100),
        )
        await session.commit()

    try:
        async with async_session_factory() as session:
            # See community-window test above re: table-wide deleted count.
            deleted = await purge_expired_audit_events(session, "trial")
            assert deleted >= 1
        async with async_session_factory() as session:
            remaining_event = (await session.execute(
                select(AuditEvent.id).where(AuditEvent.id == event.id)
            )).scalar_one_or_none()
            assert remaining_event is None
    finally:
        async with async_session_factory() as session:
            await session.execute(AuditEvent.__table__.delete().where(AuditEvent.id == event.id))
            await session.execute(SessionModel.__table__.delete().where(SessionModel.id == session_id))
            await session.commit()


@pytest.fixture
def db_session_factory_mock():
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(return_value=mock_session)
    return factory


@pytest.mark.asyncio
async def test_run_once_uses_the_decoded_plan(db_session_factory_mock):
    with patch("app.services.retention_purger.get_license_info",
               return_value=LicenseInfo(plan="business", company=None, email=None, expires_at=None)), \
         patch("app.services.retention_purger.purge_expired_audit_events",
               new_callable=AsyncMock, return_value=3) as mock_purge:
        purger = RetentionPurger(db_session_factory_mock, interval_hours=24)
        await purger.run_once()
        mock_purge.assert_called_once()
        assert mock_purge.call_args[0][1] == "business"
        assert purger.status == "healthy"


@pytest.mark.asyncio
async def test_run_once_skips_cycle_on_invalid_license_without_purging(db_session_factory_mock):
    """An invalid/expired key must not guess a plan for a destructive delete --
    skip the cycle rather than risk purging under the wrong (shorter) window."""
    with patch("app.services.retention_purger.get_license_info",
               side_effect=HTTPException(status_code=402, detail="invalid")), \
         patch("app.services.retention_purger.purge_expired_audit_events",
               new_callable=AsyncMock) as mock_purge:
        purger = RetentionPurger(db_session_factory_mock, interval_hours=24)
        await purger.run_once()
        mock_purge.assert_not_called()
        assert purger.status == "degraded"


@pytest.mark.asyncio
async def test_run_once_sets_status_degraded_on_exception(db_session_factory_mock):
    with patch("app.services.retention_purger.get_license_info",
               return_value=LicenseInfo(plan="community", company=None, email=None, expires_at=None)), \
         patch("app.services.retention_purger.purge_expired_audit_events",
               new_callable=AsyncMock, side_effect=Exception("DB error")):
        purger = RetentionPurger(db_session_factory_mock, interval_hours=24)
        await purger.run_once()
        assert purger.status == "degraded"


@pytest.mark.asyncio
async def test_stop_cancels_task(db_session_factory_mock):
    with patch("app.services.retention_purger.get_license_info",
               return_value=LicenseInfo(plan="community", company=None, email=None, expires_at=None)), \
         patch("app.services.retention_purger.purge_expired_audit_events",
               new_callable=AsyncMock, return_value=0), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        purger = RetentionPurger(db_session_factory_mock, interval_hours=24)
        purger.start()
        await asyncio.sleep(0)
        await purger.stop()
        assert purger._task is None or purger._task.cancelled()


@pytest.mark.asyncio
async def test_retention_purger_started_for_community_deployment():
    """Unlike DriftDetector, retention purge is not enterprise-gated --
    Community's 7-day window needs enforcement too (separate from
    Business's 30-day and Enterprise/Trial's 90-day windows)."""
    import app.main as _main

    with patch("app.main.has_enterprise_license", return_value=False), \
         patch("app.services.retention_purger.RetentionPurger.start"):
        async with _main.lifespan(_main.app):
            assert _main.app.state.retention_purger is not None


@pytest.mark.asyncio
async def test_license_sync_started_when_activation_code_on_file():
    """plans/v4 task 21 -- the sync job (task 20) only actually runs once
    it's wired into lifespan."""
    import app.main as _main
    from app.models.database import async_session_factory
    from app.models.user import OrgSettings

    async with async_session_factory() as db:
        row = OrgSettings(id=uuid.uuid4(), org_name="Task21 Activated Org", activation_code="task21-test-code")
        db.add(row)
        await db.commit()
        row_id = row.id

    try:
        with patch("app.main.has_enterprise_license", return_value=False), \
             patch("app.services.retention_purger.RetentionPurger.start"), \
             patch("app.services.license_sync.LicenseSync.start"):
            async with _main.lifespan(_main.app):
                assert _main.app.state.license_sync is not None
    finally:
        async with async_session_factory() as db:
            row = await db.get(OrgSettings, row_id)
            await db.delete(row)
            await db.commit()


@pytest.mark.asyncio
async def test_license_sync_not_started_without_activation_code():
    """plans/v4 task 21 -- community installs, and installs never
    activated, must not spin up the background sync task at all."""
    import app.main as _main
    from app.models.database import async_session_factory
    from app.models.user import OrgSettings
    from sqlalchemy import select

    async with async_session_factory() as db:
        existing = (
            await db.execute(select(OrgSettings).where(OrgSettings.activation_code.isnot(None)))
        ).scalars().all()
        assert not existing, (
            "dev DB already has an org with an activation_code set -- this test "
            "can't assert 'not started' while one exists; clean it up first"
        )

    with patch("app.main.has_enterprise_license", return_value=False), \
         patch("app.services.retention_purger.RetentionPurger.start"), \
         patch("app.services.license_sync.LicenseSync.start"):
        async with _main.lifespan(_main.app):
            assert _main.app.state.license_sync is None
