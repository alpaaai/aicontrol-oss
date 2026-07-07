"""ScannerPort — the stable contract every vendored admission scanner adapter implements.

Keeping this contract narrow and stable is what lets a future upstream
version bump (or a new vendored scanner, e.g. CodeGuard later) plug in
without AIControl's router/DB code changing.
"""
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel


class Finding(BaseModel):
    severity: Literal["info", "low", "medium", "high", "critical"]
    rule_id: str
    message: str
    location: str | None = None
    raw: dict = {}


class ScannerPort(Protocol):
    name: str

    async def scan(self, target: Path) -> list[Finding]:
        """Scan target, returning findings. Must never raise — malformed/adversarial
        input is caught and turned into a Finding, not an exception."""
        ...
