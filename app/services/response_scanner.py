"""Shared tool-response scanning for both the direct /intercept path
(app/routers/intercept.py) and the enterprise MCP gateway
(enterprise/mcp_gateway/main.py). Wraps agent_os.mcp_response_scanner.
MCPResponseScanner, which was previously only wired into the gateway --
the direct SDK path never scanned tool output at all before this task.

Also runs the OWASP Agent Memory Guard adapter (ASI06) for memory-write
tool calls, gated by is_memory_write(tool_name) AND an enterprise license
check — enterprise/ is optional (see app/main.py's ImportError-guarded
enterprise router imports), so this falls back to a no-op adapter when
it isn't installed. The license check is separate from the import check:
self-critique found this previously ran unconditionally on every
/intercept call whenever enterprise/ happened to be importable, with no
regard for license tier, unlike every other enterprise call-through in
this codebase.
"""
from dataclasses import replace
from typing import Any

from agent_os.mcp_response_scanner import MCPResponseScanner, MCPResponseThreat

from app.core.license_gate import get_license_info

_scanner = MCPResponseScanner()

try:
    from enterprise.app.services.memory_guard.memory_guard_adapter import (
        MemoryGuardAdapter,
        is_memory_write,
    )
    _memory_guard_adapter = MemoryGuardAdapter()
except ImportError:
    def is_memory_write(tool_name: str) -> bool:
        return False
    _memory_guard_adapter = None


def extract_response_text(response: Any) -> str:
    """Join every content[].text field for an MCP-shaped response dict;
    fall back to str() for arbitrary (non-MCP) tool return values, since
    the direct SDK path governs plain Python function calls via @control,
    not only MCP tool calls."""
    if response is None:
        return ""
    if isinstance(response, dict):
        if not response:
            return ""
        content = response.get("content")
        if isinstance(content, list):
            parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
            return " ".join(p for p in parts if p)
        return str(response)
    return str(response)


def scan_tool_response(response: Any, tool_name: str):
    text = extract_response_text(response)
    result = _scanner.scan_response(text, tool_name)

    if _memory_guard_adapter is not None and is_memory_write(tool_name) and get_license_info().is_enterprise:
        findings = _memory_guard_adapter.scan(tool_name, {"content": text})
        if findings:
            memory_threats = [
                MCPResponseThreat(category=f.rule_id, description=f.message, matched_pattern=None, details=f.raw)
                for f in findings
            ]
            result = replace(result, is_safe=False, threats=[*result.threats, *memory_threats])

    return result
