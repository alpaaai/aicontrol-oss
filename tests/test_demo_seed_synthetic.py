"""Tests for scripts/demo_seed_synthetic.py — self-service demo environment seed data.

Generates synthetic sessions/audit_events against real production agent IDs
(reused from scripts/seed.py), so every test cleans up by the DEMO_SYNTHETIC_MARKER
trigger_context before and after — the shared dev DB must not accumulate rows.
"""
from sqlalchemy import text

from app.models.database import async_session_factory
from scripts.demo_seed_synthetic import DEMO_SYNTHETIC_MARKER, generate_synthetic_data


async def _cleanup():
    async with async_session_factory() as session:
        await session.execute(
            text(
                "DELETE FROM audit_events WHERE session_id IN "
                "(SELECT id FROM sessions WHERE trigger_context = :marker)"
            ),
            {"marker": DEMO_SYNTHETIC_MARKER},
        )
        await session.execute(
            text("DELETE FROM sessions WHERE trigger_context = :marker"),
            {"marker": DEMO_SYNTHETIC_MARKER},
        )
        await session.commit()


async def _counts():
    async with async_session_factory() as session:
        session_count = (
            await session.execute(
                text("SELECT COUNT(*) FROM sessions WHERE trigger_context = :marker"),
                {"marker": DEMO_SYNTHETIC_MARKER},
            )
        ).scalar()
        event_count = (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM audit_events WHERE session_id IN "
                    "(SELECT id FROM sessions WHERE trigger_context = :marker)"
                ),
                {"marker": DEMO_SYNTHETIC_MARKER},
            )
        ).scalar()
        return session_count, event_count


async def test_generate_synthetic_data_is_idempotent():
    await _cleanup()
    try:
        await generate_synthetic_data(days=3)
        first_sessions, first_events = await _counts()
        assert first_sessions > 0
        assert first_events > 0

        await generate_synthetic_data(days=3)
        second_sessions, second_events = await _counts()

        assert second_sessions == first_sessions
        assert second_events == first_events
    finally:
        await _cleanup()


async def test_generate_synthetic_data_spans_thirty_days():
    await _cleanup()
    try:
        await generate_synthetic_data(days=30)
        async with async_session_factory() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT MIN(created_at), MAX(created_at) FROM audit_events "
                        "WHERE session_id IN "
                        "(SELECT id FROM sessions WHERE trigger_context = :marker)"
                    ),
                    {"marker": DEMO_SYNTHETIC_MARKER},
                )
            ).first()
            earliest, latest = row

        assert earliest is not None
        assert latest is not None
        assert (latest - earliest).days >= 28
    finally:
        await _cleanup()


async def test_generate_synthetic_data_has_non_degenerate_decision_mix():
    await _cleanup()
    try:
        await generate_synthetic_data(days=30)
        async with async_session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT decision, COUNT(*) FROM audit_events "
                        "WHERE session_id IN "
                        "(SELECT id FROM sessions WHERE trigger_context = :marker) "
                        "GROUP BY decision"
                    ),
                    {"marker": DEMO_SYNTHETIC_MARKER},
                )
            ).all()
            decisions = {row[0]: row[1] for row in rows}

        assert set(decisions) == {"allow", "deny", "review"}
        total = sum(decisions.values())
        for count in decisions.values():
            assert 0 < count < total
    finally:
        await _cleanup()
