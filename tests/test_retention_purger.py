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


async def _run_once_with_org(license_code_value=None, license_plan=None, activation_code=None, no_row=False):
    """Run RetentionPurger.run_once against the real org_settings table with
    the given license fields; returns (purge mock, purger). Restores the
    original org_settings rows afterwards."""
    from sqlalchemy import text
    from app.models.database import async_session_factory
    from tests.conftest import restore_org_settings, snapshot_org_settings

    async with async_session_factory() as db:
        existing = await snapshot_org_settings(db)
        await db.execute(text("DELETE FROM org_settings"))
        if not no_row:
            await db.execute(
                text("""
                    INSERT INTO org_settings (
                        id, org_name, timezone, created_at, updated_at,
                        license_key, license_plan, activation_code
                    ) VALUES (
                        gen_random_uuid(), 'Acme', 'UTC', now(), now(),
                        :license_key, :license_plan, :activation_code
                    )
                """),
                {"license_key": license_code_value, "license_plan": license_plan,
                 "activation_code": activation_code},
            )
        await db.commit()
    try:
        with patch("app.services.retention_purger.purge_expired_audit_events",
                   new_callable=AsyncMock, return_value=0) as mock_purge:
            purger = RetentionPurger(async_session_factory, interval_hours=24)
            await purger.run_once()
        return mock_purge, purger
    finally:
        async with async_session_factory() as db:
            await restore_org_settings(db, existing)
            await db.commit()


@pytest.mark.asyncio
async def test_run_once_skips_purge_for_expired_code(license_code):
    mock_purge, purger = await _run_once_with_org(license_code("enterprise", days=-1))
    mock_purge.assert_not_called()
    assert purger.status == "degraded"


@pytest.mark.asyncio
async def test_run_once_skips_purge_for_bad_signature_code(license_code):
    prefix, payload, signature = license_code("enterprise").split(".")
    flipped = ("A" if signature[0] != "A" else "B") + signature[1:]
    mock_purge, purger = await _run_once_with_org(f"{prefix}.{payload}.{flipped}")
    mock_purge.assert_not_called()
    assert purger.status == "degraded"


@pytest.mark.asyncio
async def test_run_once_skips_purge_for_legacy_paid_plan_without_code():
    mock_purge, purger = await _run_once_with_org(license_plan="business")
    mock_purge.assert_not_called()
    assert purger.status == "degraded"


@pytest.mark.asyncio
async def test_run_once_skips_purge_for_legacy_activation_code_without_key():
    mock_purge, purger = await _run_once_with_org(activation_code="ACT-123")
    mock_purge.assert_not_called()
    assert purger.status == "degraded"


@pytest.mark.asyncio
async def test_run_once_purges_with_active_codes_window(license_code):
    mock_purge, purger = await _run_once_with_org(license_code("business"))
    mock_purge.assert_called_once()
    assert mock_purge.call_args[0][1] == "business"
    assert purger.status == "healthy"


@pytest.mark.asyncio
async def test_run_once_purges_community_window_when_nothing_is_set():
    mock_purge, purger = await _run_once_with_org()
    mock_purge.assert_called_once()
    assert mock_purge.call_args[0][1] == "community"
    assert purger.status == "healthy"


@pytest.mark.asyncio
async def test_run_once_purges_community_window_with_no_org_row():
    mock_purge, purger = await _run_once_with_org(no_row=True)
    mock_purge.assert_called_once()
    assert mock_purge.call_args[0][1] == "community"


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
async def test_no_license_sync_task_is_started():
    """The billing-service daily sync was removed; an activation_code on
    file must not start any background task."""
    import app.main as _main

    with patch("app.main.has_enterprise_license", return_value=False), \
         patch("app.services.retention_purger.RetentionPurger.start"):
        async with _main.lifespan(_main.app):
            assert not hasattr(_main.app.state, "license_sync")


@pytest.mark.asyncio
async def test_purge_handles_more_expired_rows_than_one_bind_list_allows():
    """asyncpg caps a statement at 32767 bind parameters. The purge used to
    SELECT every expired id and then DELETE ... WHERE id IN (<all of them>),
    so the first purge of a busy install (tens of thousands of expired rows)
    failed on every run and the table grew without bound."""
    from sqlalchemy import text

    from app.models.database import async_session_factory

    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO audit_events
                (id, tool_name, decision, sequence_number, duration_ms, created_at)
            SELECT gen_random_uuid(), 'retention_bulk_test', 'allow', g, 1,
                   now() - interval '400 days'
            FROM generate_series(1, 33000) AS g
        """))
        await session.commit()

    async with async_session_factory() as session:
        deleted = await purge_expired_audit_events(session, "enterprise")
    assert deleted >= 33000

    async with async_session_factory() as session:
        left = (await session.execute(
            text("SELECT COUNT(*) FROM audit_events WHERE tool_name = 'retention_bulk_test'")
        )).scalar_one()
    assert left == 0
