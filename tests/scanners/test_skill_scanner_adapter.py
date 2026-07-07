"""Tests for the skill-scanner ScannerPort adapter.

Includes the hard architectural-constraint test: the adapter must never
pass --use-llm/--use-aidefense/--use-virustotal, and must actively strip
their API-key env vars even if present in the ambient environment.
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest


@pytest.fixture
def sample_scan_json():
    return json.dumps({
        "skill_name": "test-skill",
        "is_safe": False,
        "findings_count": 1,
        "findings": [
            {
                "id": "SECRET_HARDCODED_abc123",
                "rule_id": "SECRET_HARDCODED",
                "category": "secret",
                "severity": "HIGH",
                "title": "Hardcoded API key detected",
                "description": "Found what appears to be a hardcoded API key.",
                "file_path": "SKILL.md",
                "line_number": 12,
                "snippet": "api_key = 'sk-...'",
                "remediation": "Remove hardcoded credentials.",
                "analyzer": "static",
                "metadata": {},
            }
        ],
    })


@pytest.mark.asyncio
async def test_scan_maps_findings_correctly(sample_scan_json):
    from app.services.scanners.skill_scanner_adapter import SkillScannerAdapter

    adapter = SkillScannerAdapter(binary_path="/fake/skill-scanner")
    with patch(
        "app.services.scanners.skill_scanner_adapter.run_scanner_subprocess",
        new=AsyncMock(return_value=(0, sample_scan_json, "")),
    ):
        findings = await adapter.scan(Path("/some/skill"))

    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "high"
    assert f.rule_id == "SECRET_HARDCODED"
    assert f.message == "Hardcoded API key detected"
    assert f.location == "SKILL.md:12"
    assert f.raw["category"] == "secret"


@pytest.mark.asyncio
async def test_scan_returns_empty_list_for_clean_skill():
    from app.services.scanners.skill_scanner_adapter import SkillScannerAdapter

    clean_json = json.dumps({"skill_name": "clean", "is_safe": True, "findings_count": 0, "findings": []})
    adapter = SkillScannerAdapter(binary_path="/fake/skill-scanner")
    with patch(
        "app.services.scanners.skill_scanner_adapter.run_scanner_subprocess",
        new=AsyncMock(return_value=(0, clean_json, "")),
    ):
        findings = await adapter.scan(Path("/some/skill"))

    assert findings == []


@pytest.mark.asyncio
async def test_scan_never_raises_on_nonzero_exit():
    from app.services.scanners.skill_scanner_adapter import SkillScannerAdapter

    adapter = SkillScannerAdapter(binary_path="/fake/skill-scanner")
    with patch(
        "app.services.scanners.skill_scanner_adapter.run_scanner_subprocess",
        new=AsyncMock(return_value=(1, "", "Error: Directory does not exist")),
    ):
        findings = await adapter.scan(Path("/nonexistent"))

    assert len(findings) == 1
    assert findings[0].severity == "info"
    assert findings[0].rule_id == "scanner_error"


@pytest.mark.asyncio
async def test_scan_never_raises_on_malformed_json():
    from app.services.scanners.skill_scanner_adapter import SkillScannerAdapter

    adapter = SkillScannerAdapter(binary_path="/fake/skill-scanner")
    with patch(
        "app.services.scanners.skill_scanner_adapter.run_scanner_subprocess",
        new=AsyncMock(return_value=(0, "not valid json{{{", "")),
    ):
        findings = await adapter.scan(Path("/some/skill"))

    assert len(findings) == 1
    assert findings[0].rule_id == "scanner_error"


@pytest.mark.asyncio
async def test_scan_never_passes_forbidden_flags(sample_scan_json):
    """Hard architectural constraint: never enable LLM/cloud analyzers."""
    from app.services.scanners.skill_scanner_adapter import SkillScannerAdapter

    captured_cmd = {}

    async def fake_run(cmd, cwd, env, timeout_s):
        captured_cmd["cmd"] = cmd
        captured_cmd["env"] = env
        return (0, sample_scan_json, "")

    adapter = SkillScannerAdapter(binary_path="/fake/skill-scanner")
    with patch("app.services.scanners.skill_scanner_adapter.run_scanner_subprocess", new=fake_run):
        await adapter.scan(Path("/some/skill"))

    cmd = captured_cmd["cmd"]
    forbidden_flags = {"--use-llm", "--use-aidefense", "--use-virustotal", "--use-behavioral"}
    assert not (forbidden_flags & set(cmd)), f"Forbidden flag found in {cmd}"


@pytest.mark.asyncio
async def test_scan_strips_forbidden_env_vars_even_if_ambient(monkeypatch, sample_scan_json):
    """Hard architectural constraint: actively strip, don't just avoid setting."""
    monkeypatch.setenv("SKILL_SCANNER_LLM_API_KEY", "leaked-key")
    monkeypatch.setenv("AI_DEFENSE_API_KEY", "leaked-key-2")
    monkeypatch.setenv("VIRUSTOTAL_API_KEY", "leaked-key-3")

    from app.services.scanners.skill_scanner_adapter import SkillScannerAdapter

    captured_cmd = {}

    async def fake_run(cmd, cwd, env, timeout_s):
        captured_cmd["env"] = env
        return (0, sample_scan_json, "")

    adapter = SkillScannerAdapter(binary_path="/fake/skill-scanner")
    with patch("app.services.scanners.skill_scanner_adapter.run_scanner_subprocess", new=fake_run):
        await adapter.scan(Path("/some/skill"))

    env = captured_cmd["env"]
    assert "SKILL_SCANNER_LLM_API_KEY" not in env
    assert "AI_DEFENSE_API_KEY" not in env
    assert "VIRUSTOTAL_API_KEY" not in env


@pytest.mark.asyncio
async def test_scan_respects_timeout_as_info_finding():
    from app.services.scanners.skill_scanner_adapter import SkillScannerAdapter
    from app.services.scanners.subprocess_runner import ScannerTimeoutError

    adapter = SkillScannerAdapter(binary_path="/fake/skill-scanner")
    with patch(
        "app.services.scanners.skill_scanner_adapter.run_scanner_subprocess",
        new=AsyncMock(side_effect=ScannerTimeoutError("timed out")),
    ):
        findings = await adapter.scan(Path("/some/skill"))

    assert len(findings) == 1
    assert findings[0].rule_id == "scanner_timeout"
