"""Schema verification for the onboarding_identity migration."""
import pytest
from sqlalchemy import text
from app.models.database import async_session_factory


@pytest.mark.asyncio
async def test_users_table_has_new_columns():
    """Verify the 5 new onboarding columns exist on the users table."""
    expected = {"password_hash", "is_root", "invite_token_hash", "invite_expires_at", "password_set"}
    async with async_session_factory() as db:
        result = await db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = ANY(:cols)"
            ),
            {"cols": list(expected)},
        )
        found = {row[0] for row in result.fetchall()}
    assert found == expected, f"Missing columns: {expected - found}"


@pytest.mark.asyncio
async def test_org_settings_table_exists():
    """Verify org_settings table was created with the expected columns."""
    expected = {"id", "org_name", "timezone", "created_at", "updated_at"}
    async with async_session_factory() as db:
        result = await db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'org_settings'"
            )
        )
        found = {row[0] for row in result.fetchall()}
    assert found == expected, f"Unexpected org_settings columns: {found ^ expected}"
