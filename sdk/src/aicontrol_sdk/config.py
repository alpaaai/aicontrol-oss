"""Env-only SDK configuration."""
import os
from dataclasses import dataclass, field
from typing import Literal, Optional

FailMode = Literal["allow", "deny"]


@dataclass
class Config:
    url: str
    token: str = field(repr=False)
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    fail_mode: FailMode = "deny"

    @classmethod
    def from_env(cls) -> "Config":
        url = os.environ.get("AICONTROL_URL")
        if not url:
            raise ValueError("AICONTROL_URL environment variable is required")

        token = os.environ.get("AICONTROL_TOKEN")
        if not token:
            raise ValueError("AICONTROL_TOKEN environment variable is required")

        fail_mode = os.environ.get("AICONTROL_FAIL_MODE", "deny")
        if fail_mode not in ("allow", "deny"):
            raise ValueError(
                f"AICONTROL_FAIL_MODE must be 'allow' or 'deny', got {fail_mode!r}"
            )

        return cls(
            url=url,
            token=token,
            agent_id=os.environ.get("AICONTROL_AGENT_ID"),
            agent_name=os.environ.get("AICONTROL_AGENT_NAME"),
            fail_mode=fail_mode,  # type: ignore[arg-type]
        )
