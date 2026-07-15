"""Shared tool-response scanning for both the direct /intercept path
(app/routers/intercept.py) and the enterprise MCP gateway
(enterprise/mcp_gateway/main.py). Wraps agent_os.mcp_response_scanner.
MCPResponseScanner, which was previously only wired into the gateway --
the direct SDK path never scanned tool output at all before this task.
"""
from typing import Any

from agent_os.mcp_response_scanner import MCPResponseScanner

_scanner = MCPResponseScanner()


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
    return _scanner.scan_response(extract_response_text(response), tool_name)
