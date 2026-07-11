"""Tests for the cisco-ai-mcp-scanner ScannerPort adapter (WS1, business tier).

Mirrors tests/scanners/test_skill_scanner_adapter.py's mocking pattern.
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest


@pytest.fixture
def sample_raw_output():
    return json.dumps({
        "server_url": "https://mcp.example.com/mcp",
        "scan_results": [
            {
                "status": "completed",
                "is_safe": False,
                "item_type": "tool",
                "tool_name": "execute_command",
                "tool_description": "Execute shell commands",
                "findings": {
                    "yara_analyzer": {
                        "severity": "HIGH",
                        "threat_names": ["CODE EXECUTION"],
                        "threat_summary": "Detected 1 threat: code execution",
                        "total_findings": 1,
                    }
                },
            },
            {
                "status": "completed",
                "is_safe": True,
                "item_type": "tool",
                "tool_name": "safe_tool",
                "tool_description": "Does nothing dangerous",
                "findings": {
                    "yara_analyzer": {"severity": "SAFE", "threat_names": [], "threat_summary": "No threats detected", "total_findings": 0}
                },
            },
        ],
        "requested_analyzers": ["yara"],
    })


@pytest.mark.asyncio
async def test_scan_maps_unsafe_tool_findings_and_skips_safe_ones(sample_raw_output):
    from enterprise.app.services.scanners.mcp_scanner_adapter import McpScannerAdapter

    adapter = McpScannerAdapter(binary_path="/fake/mcp-scanner")
    with patch(
        "enterprise.app.services.scanners.mcp_scanner_adapter.run_scanner_subprocess",
        new=AsyncMock(return_value=(0, sample_raw_output, "")),
    ):
        findings = await adapter.scan(Path("https://mcp.example.com/mcp"))

    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "high"
    assert f.rule_id == "CODE EXECUTION"
    assert f.message == "Detected 1 threat: code execution"
    assert f.location == "execute_command"


@pytest.mark.asyncio
async def test_scan_repairs_url_double_slash_collapsed_by_path(sample_raw_output):
    """Path("https://host/x") collapses to 'https:/host/x' on str() — the
    real scan() must forward the repaired URL to the subprocess, not the
    corrupted one. Caught by an actual (non-mocked) subprocess run against
    the real installed binary during development, not a hypothetical."""
    from enterprise.app.services.scanners.mcp_scanner_adapter import McpScannerAdapter

    adapter = McpScannerAdapter(binary_path="/fake/mcp-scanner")
    mock_run = AsyncMock(return_value=(0, '{"scan_results": []}', ""))
    with patch("enterprise.app.services.scanners.mcp_scanner_adapter.run_scanner_subprocess", new=mock_run):
        await adapter.scan(Path("https://mcp.example.com/mcp"))

    called_cmd = mock_run.call_args.args[0]
    server_url = called_cmd[called_cmd.index("--server-url") + 1]
    assert server_url == "https://mcp.example.com/mcp"


@pytest.mark.asyncio
async def test_scan_never_passes_api_llm_or_virustotal_analyzers(sample_raw_output):
    from enterprise.app.services.scanners.mcp_scanner_adapter import McpScannerAdapter

    adapter = McpScannerAdapter(binary_path="/fake/mcp-scanner")
    mock_run = AsyncMock(return_value=(0, sample_raw_output, ""))
    with patch("enterprise.app.services.scanners.mcp_scanner_adapter.run_scanner_subprocess", new=mock_run):
        await adapter.scan(Path("https://mcp.example.com/mcp"))

    called_cmd = mock_run.call_args.args[0]
    assert "--analyzers" in called_cmd
    analyzers_value = called_cmd[called_cmd.index("--analyzers") + 1]
    assert analyzers_value == "yara"


@pytest.mark.asyncio
async def test_scan_strips_forbidden_env_vars_even_if_ambient():
    from enterprise.app.services.scanners.mcp_scanner_adapter import McpScannerAdapter
    import os

    adapter = McpScannerAdapter(binary_path="/fake/mcp-scanner")
    with patch.dict(os.environ, {"MCP_SCANNER_API_KEY": "leaked", "MCP_SCANNER_LLM_API_KEY": "leaked", "VIRUSTOTAL_API_KEY": "leaked"}):
        mock_run = AsyncMock(return_value=(0, '{"scan_results": []}', ""))
        with patch("enterprise.app.services.scanners.mcp_scanner_adapter.run_scanner_subprocess", new=mock_run):
            await adapter.scan(Path("https://mcp.example.com/mcp"))

    called_env = mock_run.call_args.kwargs["env"]
    assert "MCP_SCANNER_API_KEY" not in called_env
    assert "MCP_SCANNER_LLM_API_KEY" not in called_env
    assert "VIRUSTOTAL_API_KEY" not in called_env


@pytest.mark.asyncio
async def test_scan_with_auth_passes_bearer_token():
    from enterprise.app.services.scanners.mcp_scanner_adapter import McpScannerAdapter

    adapter = McpScannerAdapter(binary_path="/fake/mcp-scanner")
    mock_run = AsyncMock(return_value=(0, '{"scan_results": []}', ""))
    with patch("enterprise.app.services.scanners.mcp_scanner_adapter.run_scanner_subprocess", new=mock_run):
        await adapter.scan_with_auth("https://mcp.example.com/mcp", bearer_token="secret-token")

    called_cmd = mock_run.call_args.args[0]
    assert "--bearer-token" in called_cmd
    assert "secret-token" in called_cmd


@pytest.mark.asyncio
async def test_scan_returns_empty_list_for_clean_server():
    from enterprise.app.services.scanners.mcp_scanner_adapter import McpScannerAdapter

    adapter = McpScannerAdapter(binary_path="/fake/mcp-scanner")
    with patch(
        "enterprise.app.services.scanners.mcp_scanner_adapter.run_scanner_subprocess",
        new=AsyncMock(return_value=(0, '{"scan_results": []}', "")),
    ):
        findings = await adapter.scan(Path("https://clean.example.com/mcp"))
    assert findings == []


@pytest.mark.asyncio
async def test_scan_timeout_returns_info_finding():
    from enterprise.app.services.scanners.mcp_scanner_adapter import McpScannerAdapter
    from app.services.scanners.subprocess_runner import ScannerTimeoutError

    adapter = McpScannerAdapter(binary_path="/fake/mcp-scanner")
    with patch(
        "enterprise.app.services.scanners.mcp_scanner_adapter.run_scanner_subprocess",
        new=AsyncMock(side_effect=ScannerTimeoutError("timed out")),
    ):
        findings = await adapter.scan(Path("https://slow.example.com/mcp"))
    assert len(findings) == 1
    assert findings[0].rule_id == "scanner_timeout"
