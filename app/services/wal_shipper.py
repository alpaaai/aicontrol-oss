"""Background task that drains the WAL (app.services.wal.WalWriter's output
file) into Postgres, off the /intercept hot path. See app/services/wal.py's
module docstring for the durability principle this implements.

Checkpoint: a sibling `<wal_path>.checkpoint` file holding the last
successfully-shipped wal_seq. Advances only after the Postgres commit
succeeds, so a crash between commit and checkpoint write re-ships (and
re-inserts under the same event_id — a no-op ON CONFLICT would be needed for
true idempotency; this plan accepts occasional duplicate-key IntegrityErrors
on replay as a caught, logged, skip-and-continue case, since losing an audit
row is worse than a harmless duplicate-insert failure).
"""
import asyncio
import json
import uuid
from pathlib import Path
from typing import Callable

from sqlalchemy.exc import IntegrityError

from app.core.logging import get_logger
from app.services.audit_writer import write_event

logger = get_logger("wal_shipper")


class WalShipper:
    def __init__(self, wal_path: Path, session_factory: Callable, ship_interval_s: float = 0.2):
        self.wal_path = Path(wal_path)
        self.checkpoint_path = self.wal_path.with_suffix(self.wal_path.suffix + ".checkpoint")
        self.session_factory = session_factory
        self.ship_interval_s = ship_interval_s
        self._task: asyncio.Task | None = None

    def _read_checkpoint(self) -> int:
        if not self.checkpoint_path.exists():
            return -1
        return int(self.checkpoint_path.read_text().strip() or -1)

    def _write_checkpoint(self, wal_seq: int) -> None:
        self.checkpoint_path.write_text(str(wal_seq))

    async def _ship_once(self) -> int:
        """Ship every WAL line with wal_seq > checkpoint. Returns count shipped."""
        if not self.wal_path.exists():
            return 0

        checkpoint = self._read_checkpoint()
        pending = []
        with open(self.wal_path, "r") as f:
            for raw_line in f:
                line = json.loads(raw_line)
                if line["wal_seq"] > checkpoint:
                    pending.append(line)

        if not pending:
            return 0

        shipped = 0
        async with self.session_factory() as session:
            for line in pending:
                try:
                    await write_event(
                        session=session,
                        event_id=uuid.UUID(line["event_id"]),
                        session_id=uuid.UUID(line["session_id"]) if line.get("session_id") else None,
                        agent_id=uuid.UUID(line["agent_id"]) if line.get("agent_id") else None,
                        agent_name=line.get("agent_name"),
                        tool_name=line["tool_name"],
                        tool_parameters=line.get("tool_parameters"),
                        decision=line["decision"],
                        decision_reason=line["decision_reason"],
                        sequence_number=line["sequence_number"],
                        duration_ms=line["duration_ms"],
                        policy_id=uuid.UUID(line["policy_id"]) if line.get("policy_id") else None,
                        policy_name=line.get("policy_name"),
                        tool_response=line.get("tool_response"),
                        risk_delta=line.get("risk_delta", 0),
                        input_tokens=line.get("input_tokens"),
                        output_tokens=line.get("output_tokens"),
                        cost_usd=line.get("cost_usd"),
                        bypass=line.get("bypass", False),
                        enforced=line.get("enforced", True),
                    )
                    shipped += 1
                except IntegrityError:
                    logger.warning("wal_ship_duplicate_skipped", event_id=line["event_id"])
                    await session.rollback()
                    continue
                self._write_checkpoint(line["wal_seq"])
            await session.commit()

        logger.info("wal_shipped", count=shipped)
        return shipped

    async def replay_and_start(self) -> None:
        """Ship any lines left over from before a crash, then start the periodic loop."""
        await self._ship_once()
        self._task = asyncio.create_task(self._run(), name="wal_shipper")
        logger.info("wal_shipper_started", ship_interval_s=self.ship_interval_s)

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.ship_interval_s)
            try:
                await self._ship_once()
            except Exception as exc:
                logger.error("wal_ship_cycle_failed", error=str(exc))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("wal_shipper_stopped")
