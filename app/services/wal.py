"""Durable-append audit WAL — local append-only log, background-shipped to Postgres.

Principle: fail-open on enforcement, never-lose on audit. Each intercept call
appends one JSON line to a local file and fsyncs it (microseconds) before
returning — the Postgres write happens later, off the request's hot path, via
WalShipper (app/services/wal_shipper.py). On crash, unshipped lines are
replayed from this file at next startup (see WalShipper.replay_and_start).

WAL lines carry the same fields as app.services.audit_writer.write_event's
kwargs, plus wal_seq (this file's local monotonic line index) and event_id
(pre-generated here so the caller can return it immediately, before the
Postgres row exists).
"""
import json
import os
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings


class WalWriter:
    def __init__(self, wal_path: Path):
        self.wal_path = Path(wal_path)
        self.wal_path.parent.mkdir(parents=True, exist_ok=True)
        self._next_seq = self._count_existing_lines()

    def _count_existing_lines(self) -> int:
        if not self.wal_path.exists():
            return 0
        with open(self.wal_path, "r") as f:
            return sum(1 for _ in f)

    def append(self, event: dict[str, Any]) -> uuid.UUID:
        """Append one event to the WAL, fsync, and return its pre-generated event_id."""
        event_id = uuid.uuid4()
        line = {**event, "event_id": str(event_id), "wal_seq": self._next_seq}
        with open(self.wal_path, "a") as f:
            f.write(json.dumps(line, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self._next_seq += 1
        return event_id

    def reset_for_tests(self) -> None:
        """Truncate the WAL file and its checkpoint. Test-support only — no
        production code path calls this. Needed because ASGITransport-based
        tests (in-process, no live WalShipper) never advance the checkpoint,
        so unshipped entries from one test would otherwise persist and
        inflate count_unshipped_for_session_tool for later tests reusing the
        same session_id/tool_name."""
        if self.wal_path.exists():
            self.wal_path.unlink()
        checkpoint_path = self.wal_path.with_suffix(self.wal_path.suffix + ".checkpoint")
        if checkpoint_path.exists():
            checkpoint_path.unlink()
        self._next_seq = 0


def count_unshipped_for_session_tool(wal_path: Path, session_id: str, tool_name: str) -> int:
    """Count WAL lines not yet shipped to Postgres for (session_id, tool_name).

    Rate-limit and token-budget cumulative counts query audit_events in
    Postgres, but allow/deny writes now land there asynchronously (via
    WalShipper, on a ship_interval_s lag) rather than synchronously. Without
    this, a burst of calls in the same session could undercount and bypass a
    session-scoped rate limit or budget during that lag window — this makes
    the count correct regardless of shipping lag.
    """
    wal_path = Path(wal_path)
    checkpoint_path = wal_path.with_suffix(wal_path.suffix + ".checkpoint")
    checkpoint = -1
    if checkpoint_path.exists():
        checkpoint = int(checkpoint_path.read_text().strip() or -1)

    if not wal_path.exists():
        return 0

    count = 0
    with open(wal_path, "r") as f:
        for raw_line in f:
            line = json.loads(raw_line)
            if (
                line["wal_seq"] > checkpoint
                and line.get("session_id") == session_id
                and line.get("tool_name") == tool_name
            ):
                count += 1
    return count


def sum_unshipped_for_session_tool(
    wal_path: Path, session_id: str, tool_name: str
) -> tuple[float, float]:
    """Sum (input_tokens + output_tokens, cost_usd) across WAL lines not yet
    shipped to Postgres for (session_id, tool_name). Same rationale as
    count_unshipped_for_session_tool — token_budget cumulative sums query
    audit_events directly, but writes land there asynchronously, so a burst
    of calls within the shipping lag could undercount and bypass a budget."""
    wal_path = Path(wal_path)
    checkpoint_path = wal_path.with_suffix(wal_path.suffix + ".checkpoint")
    checkpoint = -1
    if checkpoint_path.exists():
        checkpoint = int(checkpoint_path.read_text().strip() or -1)

    if not wal_path.exists():
        return 0.0, 0.0

    tokens = 0.0
    cost = 0.0
    with open(wal_path, "r") as f:
        for raw_line in f:
            line = json.loads(raw_line)
            if (
                line["wal_seq"] > checkpoint
                and line.get("session_id") == session_id
                and line.get("tool_name") == tool_name
            ):
                tokens += (line.get("input_tokens") or 0) + (line.get("output_tokens") or 0)
                cost += line.get("cost_usd") or 0
    return tokens, cost


# Module-level singleton: importable directly (no app.state dependency), so
# it's available even to in-process ASGITransport tests that skip the
# FastAPI lifespan (a common pattern in this codebase's test suite).
default_wal_writer = WalWriter(Path(settings.WAL_DIR) / "audit.jsonl")
