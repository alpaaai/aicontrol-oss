import pytest

from app.models.database import async_session_factory


@pytest.mark.asyncio
async def test_promote_candidate_requires_explicit_owner():
    from enterprise.app.services.discovery.promotion import promote_candidate

    async with async_session_factory() as session:
        with pytest.raises(ValueError, match="owner is required"):
            await promote_candidate(session, candidate_id="00000000-0000-0000-0000-000000000000", owner=None)
