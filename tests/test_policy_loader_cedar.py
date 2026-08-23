"""The loader compiles each seed policy to Cedar and stores the source."""
import pytest
from cedarpy import PolicySet
from sqlalchemy import select

from app.models.schemas import Policy
from app.services.policy_loader import load_all, load_yaml


def test_every_seed_policy_declares_an_effect():
    for p in load_yaml():
        assert p["effect"] in ("deny", "review"), p["name"]


def test_no_seed_policy_still_uses_rule_type():
    for p in load_yaml():
        assert "rule_type" not in p, p["name"]


@pytest.mark.asyncio
async def test_load_all_stores_parseable_cedar_text(db_session):
    await load_all(db_session)
    rows = (await db_session.execute(select(Policy))).scalars().all()
    assert rows, "loader inserted no policies"
    for row in rows:
        assert row.cedar_text, f"{row.name} has no cedar_text"
        PolicySet.from_str(row.cedar_text + "\npermit (principal, action, resource);")
