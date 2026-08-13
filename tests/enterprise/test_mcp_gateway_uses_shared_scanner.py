"""Task 3 Step 7-8: enterprise/mcp_gateway/main.py must route its post-call
response scan through app.services.response_scanner.scan_tool_response()
instead of instantiating its own MCPResponseScanner() -- confirmed this
session (enterprise/mcp_gateway/main.py:19,37,152) that it never called
response_scanner.py before this task, so Memory Guard (wired into
scan_tool_response in Task 3 Step 5-6) never covered the gateway path.

No standalone `handle_tool_response`/similar function existed in the gateway
source to call directly (the plan draft's Step 7 test guessed one) -- the
scan+audit logic was inline inside call_tool(). Extracted into
_finalize_response(), the real, directly-testable unit this test exercises.
"""
from agent_os.mcp_response_scanner import MCPResponseScanResult


def test_finalize_response_calls_shared_response_scanner(monkeypatch):
    import enterprise.mcp_gateway.main as gw

    called = {}

    def fake_scan_tool_response(response, tool_name):
        called["tool_name"] = tool_name
        return MCPResponseScanResult(is_safe=True, tool_name=tool_name, threats=[])

    monkeypatch.setattr(gw.response_scanner, "scan_tool_response", fake_scan_tool_response)

    result = gw._finalize_response({"content": []}, "save_memory", server_name="test-server")

    assert called["tool_name"] == "save_memory"
    assert result == {"content": []}


def test_finalize_response_blocks_when_scan_flags_and_policy_is_block(monkeypatch):
    import enterprise.mcp_gateway.main as gw
    from agent_os.mcp_response_scanner import MCPResponseThreat

    def fake_scan_tool_response(response, tool_name):
        return MCPResponseScanResult(
            is_safe=False, tool_name=tool_name,
            threats=[MCPResponseThreat(category="memory_guard:prompt_injection", description="hit", matched_pattern=None, details={})],
        )

    monkeypatch.setattr(gw.response_scanner, "scan_tool_response", fake_scan_tool_response)
    monkeypatch.setattr(gw.settings, "MCP_RESPONSE_SCAN_POLICY", "block")

    result = gw._finalize_response({"content": [{"type": "text", "text": "x"}]}, "save_memory", server_name="test-server")

    assert result["isError"] is True
