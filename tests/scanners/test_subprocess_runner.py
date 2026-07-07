"""Tests for the shared subprocess execution helper used by scanner adapters."""
import asyncio
import time
import pytest


@pytest.mark.asyncio
async def test_run_scanner_subprocess_returns_exit_code_and_stdout():
    from app.services.scanners.subprocess_runner import run_scanner_subprocess

    exit_code, stdout, stderr = await run_scanner_subprocess(
        ["echo", "hello"], cwd=None, env={}, timeout_s=5.0
    )
    assert exit_code == 0
    assert stdout.strip() == "hello"


@pytest.mark.asyncio
async def test_run_scanner_subprocess_enforces_timeout():
    from app.services.scanners.subprocess_runner import run_scanner_subprocess, ScannerTimeoutError

    with pytest.raises(ScannerTimeoutError):
        await run_scanner_subprocess(["sleep", "5"], cwd=None, env={}, timeout_s=0.3)


@pytest.mark.asyncio
async def test_run_scanner_subprocess_does_not_block_event_loop():
    from app.services.scanners.subprocess_runner import run_scanner_subprocess

    async def ticker():
        ticks = 0
        for _ in range(5):
            await asyncio.sleep(0.05)
            ticks += 1
        return ticks

    start = time.monotonic()
    ticker_task = asyncio.create_task(ticker())
    exit_code, _, _ = await run_scanner_subprocess(["sleep", "0.3"], cwd=None, env={}, timeout_s=5.0)
    ticks = await ticker_task
    elapsed = time.monotonic() - start

    assert exit_code == 0
    assert ticks == 5
    assert elapsed < 0.6


@pytest.mark.asyncio
async def test_run_scanner_subprocess_caps_captured_output_size():
    import os
    from app.services.scanners.subprocess_runner import run_scanner_subprocess

    exit_code, stdout, _ = await run_scanner_subprocess(
        ["python3", "-c", "print('x' * 10_000_000)"],
        cwd=None, env={"PATH": os.environ["PATH"]}, timeout_s=5.0, max_output_bytes=1000,
    )
    assert len(stdout.encode()) <= 1000 + 100  # small slack for truncation marker


@pytest.mark.asyncio
async def test_run_scanner_subprocess_never_uses_shell():
    """A malicious-looking argv element must not be shell-interpreted."""
    from app.services.scanners.subprocess_runner import run_scanner_subprocess

    exit_code, stdout, _ = await run_scanner_subprocess(
        ["echo", "$(echo pwned)"], cwd=None, env={}, timeout_s=5.0
    )
    assert stdout.strip() == "$(echo pwned)"
