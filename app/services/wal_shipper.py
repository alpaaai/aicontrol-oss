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
import os
import uuid
from pathlib import Path
from typing import Callable

from sqlalchemy.exc import IntegrityError

from app.core.logging import get_logger
from app.models.schemas import AuditEvent
from app.services.audit_writer import write_event
from app.services.wal import checkpoint_path_for, iter_wal_lines, read_checkpoint

logger = get_logger("wal_shipper")

# Failure handling: a line that fails to ship is retried on later cycles
# (the usual cause is the request that appended it not having committed its
# sessions row yet, which resolves in milliseconds). Order is preserved, so a
# failing line holds back later ones until it ships or exhausts max_attempts,
# at which point it moves to the dead-letter file and shipping continues --
# one permanently unshippable line must not stall the audit trail forever.
DEFAULT_MAX_ATTEMPTS = 25
# Shipped lines are compacted out of the WAL once it grows past this size.
DEFAULT_COMPACT_THRESHOLD_BYTES = 1_048_576


class WalShipper:
    def __init__(
        self,
        wal_path: Path,
        session_factory: Callable,
        ship_interval_s: float = 0.2,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        compact_threshold_bytes: int = DEFAULT_COMPACT_THRESHOLD_BYTES,
    ):
        self.wal_path = Path(wal_path)
        self.checkpoint_path = checkpoint_path_for(self.wal_path)
        self.dead_letter_path = self.wal_path.with_suffix(self.wal_path.suffix + ".deadletter")
        self.session_factory = session_factory
        self.ship_interval_s = ship_interval_s
        self.max_attempts = max_attempts
        self.compact_threshold_bytes = compact_threshold_bytes
        self._task: asyncio.Task | None = None
        self._attempts: dict[int, int] = {}
        self.dead_lettered = 0

    def _read_checkpoint(self) -> int:
        return read_checkpoint(self.wal_path)

    def _write_checkpoint(self, wal_seq: int) -> None:
        tmp = self.checkpoint_path.with_suffix(self.checkpoint_path.suffix + ".tmp")
        tmp.write_text(str(wal_seq))
        os.replace(tmp, self.checkpoint_path)

    def pending_count(self) -> int:
        """Number of WAL lines not yet shipped to Postgres."""
        checkpoint = self._read_checkpoint()
        return sum(1 for line in iter_wal_lines(self.wal_path) if line["wal_seq"] > checkpoint)

    async def _write_line(self, line: dict) -> None:
        async with self.session_factory() as session:
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
                workflow=line.get("workflow"),
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
            await session.commit()

    async def _already_in_postgres(self, line: dict) -> bool:
        try:
            event_id = uuid.UUID(line["event_id"])
        except (KeyError, ValueError, TypeError):
            return False
        async with self.session_factory() as session:
            return await session.get(AuditEvent, event_id) is not None

    def _dead_letter(self, line: dict, error: Exception) -> None:
        with open(self.dead_letter_path, "a") as f:
            f.write(json.dumps({**line, "_ship_error": f"{type(error).__name__}: {error}"}, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self.dead_lettered += 1
        logger.error(
            "wal_line_dead_lettered", wal_seq=line["wal_seq"], event_id=line.get("event_id"),
            error=str(error), dead_letter_path=str(self.dead_letter_path),
        )

    def _compact(self) -> None:
        """Drop shipped lines from the WAL. Synchronous end to end (no await)
        so the in-process WalWriter cannot append between the read and the
        replace. Written to a temp file and renamed so a crash leaves either
        the old or the new file, never a partial one."""
        if not self.wal_path.exists() or self.wal_path.stat().st_size < self.compact_threshold_bytes:
            return
        checkpoint = self._read_checkpoint()
        tmp = self.wal_path.with_suffix(self.wal_path.suffix + ".tmp")
        with open(tmp, "w") as f:
            for line in iter_wal_lines(self.wal_path):
                if line["wal_seq"] > checkpoint:
                    f.write(json.dumps(line, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.wal_path)

    async def _ship_once(self) -> int:
        """Ship every WAL line with wal_seq > checkpoint, in order. Returns count shipped."""
        checkpoint = self._read_checkpoint()
        pending = sorted(
            (line for line in iter_wal_lines(self.wal_path) if line["wal_seq"] > checkpoint),
            key=lambda line: line["wal_seq"],
        )
        if not pending:
            self._compact()
            return 0

        shipped = 0
        for line in pending:
            seq = line["wal_seq"]
            try:
                # Each line commits on its own session, so a later line's
                # failure can never roll back an earlier line's insert.
                await self._write_line(line)
                shipped += 1
            except Exception as exc:
                # A primary-key collision means a crash re-shipped a line that
                # had already committed: done, advance. Any other failure
                # (FK to a sessions row that has not committed yet, bad data)
                # is NOT a duplicate and must not be skipped past.
                if isinstance(exc, IntegrityError) and await self._already_in_postgres(line):
                    logger.warning("wal_ship_duplicate_skipped", event_id=line.get("event_id"))
                else:
                    attempts = self._attempts.get(seq, 0) + 1
                    if attempts < self.max_attempts:
                        self._attempts[seq] = attempts
                        logger.warning(
                            "wal_ship_line_failed", wal_seq=seq, attempt=attempts,
                            max_attempts=self.max_attempts, error=f"{type(exc).__name__}: {exc}",
                        )
                        break
                    self._dead_letter(line, exc)
            self._attempts.pop(seq, None)
            self._write_checkpoint(seq)

        if shipped:
            logger.info("wal_shipped", count=shipped)
        self._compact()
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
