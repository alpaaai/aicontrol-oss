"""Loads policies from YAML, compiles them to Cedar, upserts to Postgres."""
import uuid
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from sqlalchemy import select
from app.models.schemas import Policy
from app.services.policy_compiler import compile_policy

logger = get_logger("policy_loader")

POLICIES_YAML = Path(__file__).parent.parent.parent / "policies" / "policies.yaml"
DEMO_SEEDS_DIR = Path(__file__).parent.parent.parent / "policies" / "demo_seeds"


def load_yaml(path: Path = POLICIES_YAML) -> list[dict[str, Any]]:
    """Read and parse a policies-shaped YAML file. Defaults to policies.yaml
    (the default shipped seed); pass a path under policies/demo_seeds/ to
    load a scenario's demo-only policies instead."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["policies"]


async def upsert_policies(session: AsyncSession, policies: list[dict]) -> None:
    """Insert or update each policy row, compiling its Cedar source on the way in.

    Compilation happens here rather than at evaluation time so the hot path
    never parses a condition dict.
    """
    for p in policies:
        row = Policy(
            name=p["name"],
            description=p.get("description", ""),
            condition=p["condition"],
            principal_type=p.get("principal_type"),
            principal_id=p.get("principal_id"),
            action_tool=p.get("action_tool"),
            resource_system=p.get("resource_system"),
            effect=p["effect"],
            severity=p.get("severity", "medium"),
            active=p.get("active", True),
            compliance_frameworks=p.get("compliance_frameworks", []),
            library=p.get("library", False),
            priority=p.get("priority", 100),
            category=p.get("category"),
        )
        existing = (await session.execute(
            select(Policy).where(Policy.name == row.name)
        )).scalar_one_or_none()
        row.id = existing.id if existing else uuid.uuid4()
        row.cedar_text = compile_policy(row)
        await session.merge(row)
    await session.commit()
    logger.info("policies_upserted", count=len(policies))


async def load_all(session: AsyncSession) -> None:
    """Full startup sequence: YAML -> compile -> Postgres."""
    policies = load_yaml()
    await upsert_policies(session, policies)
