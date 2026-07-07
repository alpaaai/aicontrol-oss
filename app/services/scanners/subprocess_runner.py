"""Shared subprocess execution helper for vendored scanner adapters.

Scanner subprocesses analyze untrusted, potentially adversarial content by
design — this helper treats the subprocess itself as a potential attack
surface: no shell=True, explicit argv list, hard timeout, and a cap on
captured output size to avoid a runaway-output memory bomb.
"""
import asyncio
import resource
import subprocess
from typing import Optional


class ScannerTimeoutError(Exception):
    """Raised when a scanner subprocess exceeds its timeout and is killed."""


def _run_blocking(
    cmd: list[str],
    cwd: Optional[str],
    env: dict,
    timeout_s: float,
    max_output_bytes: int,
) -> tuple[int, str, str]:
    def _limit_resources():
        # 60s CPU time cap and 1GB address-space cap — defense in depth against
        # a malicious scan target causing runaway scanner resource use.
        resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
        resource.setrlimit(resource.RLIMIT_AS, (1_073_741_824, 1_073_741_824))

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            timeout=timeout_s,
            capture_output=True,
            text=True,
            shell=False,
            preexec_fn=_limit_resources,
        )
    except subprocess.TimeoutExpired as exc:
        raise ScannerTimeoutError(f"Scanner subprocess exceeded {timeout_s}s: {cmd[0]}") from exc

    def _cap(s: str) -> str:
        encoded = s.encode()
        if len(encoded) <= max_output_bytes:
            return s
        return encoded[:max_output_bytes].decode(errors="ignore") + "...[truncated]"

    return result.returncode, _cap(result.stdout), _cap(result.stderr)


async def run_scanner_subprocess(
    cmd: list[str],
    cwd: Optional[str],
    env: dict,
    timeout_s: float,
    max_output_bytes: int = 5_000_000,
) -> tuple[int, str, str]:
    """Run cmd in a thread (never blocks the event loop), enforcing timeout
    and output-size caps. Returns (exit_code, stdout, stderr)."""
    return await asyncio.to_thread(_run_blocking, cmd, cwd, env, timeout_s, max_output_bytes)
