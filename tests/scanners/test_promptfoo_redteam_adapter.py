"""Tests for the Promptfoo named-plugin admission red-team ScannerPort adapter.

Promptfoo's own CLI splits red-teaming into two subprocess calls: `redteam
generate` (LLM-backed attack-probe generation, out of this adapter's control —
confirmed against the installed package's own --help text, whose --provider
default is an OpenAI model) and `eval --output <path>.json` (deterministic
evaluation against the target, JSON parsed by this adapter). `redteam run
--output json` does NOT produce evaluation JSON — that flag only controls
where the generated-tests file is written, confirmed by reading main.js.
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest


def _eval_json(results):
    return json.dumps({
        "evalId": "eval-abc123",
        "results": {"version": 3, "timestamp": "2026-08-13T00:00:00Z", "results": results, "prompts": [], "stats": {}},
        "config": {},
    })


@pytest.mark.asyncio
async def test_scan_reports_promptfoo_findings():
    from app.services.scanners.promptfoo_redteam_adapter import PromptfooRedteamAdapter

    eval_output = _eval_json([
        {
            "success": False,
            "testCase": {"metadata": {"pluginId": "agentic:memory-poisoning"}},
            "gradingResult": {"reason": "Agent accepted a poisoned memory write."},
        },
    ])

    adapter = PromptfooRedteamAdapter(binary_path="/fake/promptfoo")
    with patch(
        "app.services.scanners.promptfoo_redteam_adapter.run_scanner_subprocess",
        new=AsyncMock(side_effect=[(0, "", ""), (0, "", "")]),
    ), patch(
        "app.services.scanners.promptfoo_redteam_adapter._read_json_file",
        return_value=json.loads(eval_output),
    ):
        findings = await adapter.scan(Path("/some/target.yaml"))

    assert any(f.rule_id.startswith("promptfoo:") for f in findings)
    assert findings[0].rule_id == "promptfoo:agentic:memory-poisoning"
    assert findings[0].severity == "high"
    assert findings[0].message == "Agent accepted a poisoned memory write."


@pytest.mark.asyncio
async def test_scan_skips_successful_defenses():
    from app.services.scanners.promptfoo_redteam_adapter import PromptfooRedteamAdapter

    eval_output = _eval_json([
        {"success": True, "testCase": {"metadata": {"pluginId": "hijacking"}}, "gradingResult": {"reason": "blocked"}},
    ])

    adapter = PromptfooRedteamAdapter(binary_path="/fake/promptfoo")
    with patch(
        "app.services.scanners.promptfoo_redteam_adapter.run_scanner_subprocess",
        new=AsyncMock(side_effect=[(0, "", ""), (0, "", "")]),
    ), patch(
        "app.services.scanners.promptfoo_redteam_adapter._read_json_file",
        return_value=json.loads(eval_output),
    ):
        findings = await adapter.scan(Path("/some/target.yaml"))

    assert findings == []


@pytest.mark.asyncio
async def test_scan_never_raises_on_generate_step_nonzero_exit():
    from app.services.scanners.promptfoo_redteam_adapter import PromptfooRedteamAdapter

    adapter = PromptfooRedteamAdapter(binary_path="/fake/promptfoo")
    with patch(
        "app.services.scanners.promptfoo_redteam_adapter.run_scanner_subprocess",
        new=AsyncMock(return_value=(1, "", "generation provider unreachable")),
    ):
        findings = await adapter.scan(Path("/some/target.yaml"))

    assert len(findings) == 1
    assert findings[0].rule_id == "scanner_error"


@pytest.mark.asyncio
async def test_scan_never_raises_on_eval_step_nonzero_exit():
    from app.services.scanners.promptfoo_redteam_adapter import PromptfooRedteamAdapter

    adapter = PromptfooRedteamAdapter(binary_path="/fake/promptfoo")
    with patch(
        "app.services.scanners.promptfoo_redteam_adapter.run_scanner_subprocess",
        new=AsyncMock(side_effect=[(0, "", ""), (1, "", "eval crashed")]),
    ):
        findings = await adapter.scan(Path("/some/target.yaml"))

    assert len(findings) == 1
    assert findings[0].rule_id == "scanner_error"


@pytest.mark.asyncio
async def test_scan_never_raises_on_malformed_eval_output():
    from app.services.scanners.promptfoo_redteam_adapter import PromptfooRedteamAdapter

    adapter = PromptfooRedteamAdapter(binary_path="/fake/promptfoo")
    with patch(
        "app.services.scanners.promptfoo_redteam_adapter.run_scanner_subprocess",
        new=AsyncMock(side_effect=[(0, "", ""), (0, "", "")]),
    ), patch(
        "app.services.scanners.promptfoo_redteam_adapter._read_json_file",
        side_effect=FileNotFoundError("no such file"),
    ):
        findings = await adapter.scan(Path("/some/target.yaml"))

    assert len(findings) == 1
    assert findings[0].rule_id == "scanner_error"


@pytest.mark.asyncio
async def test_scan_respects_timeout_as_info_finding():
    from app.services.scanners.promptfoo_redteam_adapter import PromptfooRedteamAdapter
    from app.services.scanners.subprocess_runner import ScannerTimeoutError

    adapter = PromptfooRedteamAdapter(binary_path="/fake/promptfoo")
    with patch(
        "app.services.scanners.promptfoo_redteam_adapter.run_scanner_subprocess",
        new=AsyncMock(side_effect=ScannerTimeoutError("timed out")),
    ):
        findings = await adapter.scan(Path("/some/target.yaml"))

    assert len(findings) == 1
    assert findings[0].rule_id == "scanner_timeout"
