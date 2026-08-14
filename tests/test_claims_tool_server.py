from fastapi.testclient import TestClient

from scripts.demos.fixture_mcp_servers.claims_tool_server import app

client = TestClient(app)


def test_tools_list_returns_all_three_tools():
    resp = client.post("/tools/list", json={})
    names = {t["name"] for t in resp.json()["tools"]}
    assert names == {"get_claim_status", "leak_creds_tool", "export_all_claims"}


def test_call_get_claim_status_returns_clean_text():
    resp = client.post("/call_tool", json={"name": "get_claim_status", "arguments": {"claim_id": "CLM-2024-08847"}})
    data = resp.json()
    assert data["isError"] is False
    assert "CLM-2024-08847" in data["content"][0]["text"]


def test_call_leak_creds_tool_response_contains_aws_key_and_system_tag():
    resp = client.post("/call_tool", json={"name": "leak_creds_tool", "arguments": {}})
    text = resp.json()["content"][0]["text"]
    assert "AKIA" in text
    assert "[SYSTEM]" in text or "[system]" in text.lower()


def test_call_unknown_tool_returns_error():
    resp = client.post("/call_tool", json={"name": "nonexistent_tool", "arguments": {}})
    assert resp.json()["isError"] is True
