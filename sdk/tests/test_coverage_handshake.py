"""Every adapter reports its coverage when it binds.

An adapter that binds silently leaves "installed but never firing" and "never
installed" indistinguishable on the server -- which is the state the coverage
feature exists to surface.
"""
import sys
from types import ModuleType

import pytest

from aicontrol_sdk.adapters.anthropic_agent_sdk import AnthropicAgentSDKAdapter
from aicontrol_sdk.adapters.crewai_adapter import CrewAIAdapter
from aicontrol_sdk.adapters.google_adk import GoogleADKAdapter
from aicontrol_sdk.adapters.langgraph_adapter import LangGraphAdapter
from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter

ALL_ADAPTERS = [
    OpenAIAgentsSDKAdapter, LangGraphAdapter, GoogleADKAdapter,
    AnthropicAgentSDKAdapter, CrewAIAdapter,
]


class _RecordingClient:
    def __init__(self):
        self.calls = []

    def report_coverage(self, **kwargs):
        self.calls.append(kwargs)


@pytest.fixture
def client():
    return _RecordingClient()


def _stub_framework(adapter, monkeypatch):
    """Stand in for the framework package each patch() imports."""
    if adapter.name == "openai_agents":
        agents = ModuleType("agents")

        class _Runner:
            @classmethod
            def run(cls, *a, **k):
                pass

            @classmethod
            def run_sync(cls, *a, **k):
                pass

            @classmethod
            def run_streamed(cls, *a, **k):
                pass

        agents.Runner = _Runner
        monkeypatch.setitem(sys.modules, "agents", agents)
    elif adapter.name == "google_adk":
        runners = ModuleType("google.adk.runners")

        class _Runner:
            def __init__(self, *a, **k):
                pass

        runners.Runner = _Runner
        monkeypatch.setitem(sys.modules, "google", ModuleType("google"))
        monkeypatch.setitem(sys.modules, "google.adk", ModuleType("google.adk"))
        monkeypatch.setitem(sys.modules, "google.adk.runners", runners)
    elif adapter.name == "anthropic":
        sdk = ModuleType("claude_agent_sdk")

        class _Options:
            def __init__(self, *a, **k):
                pass

        class _Client:
            def receive_messages(self):
                pass

        sdk.ClaudeAgentOptions = _Options
        sdk.ClaudeSDKClient = _Client
        sdk.query = lambda *a, **k: None
        monkeypatch.setitem(sys.modules, "claude_agent_sdk", sdk)
    elif adapter.name == "crewai":
        hooks = ModuleType("crewai.hooks")
        hooks.register_before_tool_call_hook = lambda fn: None
        hooks.register_after_tool_call_hook = lambda fn: None
        monkeypatch.setitem(sys.modules, "crewai", ModuleType("crewai"))
        monkeypatch.setitem(sys.modules, "crewai.hooks", hooks)


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS, ids=lambda c: c.__name__)
def test_patch_reports_coverage_once_with_its_own_framework_name(
    adapter_cls, client, monkeypatch
):
    adapter = adapter_cls()
    _stub_framework(adapter, monkeypatch)
    adapter.patch(client)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["framework"] == adapter.name
    assert call["hook"]
    assert call["sdk_version"]
    assert call["workflow"] == "unassigned"
    assert call["silent_noop_warnings"] == []


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS, ids=lambda c: c.__name__)
def test_the_declared_workflow_is_reported(adapter_cls, client, monkeypatch):
    adapter = adapter_cls()
    _stub_framework(adapter, monkeypatch)
    adapter.patch(client, workflow="claims_intake")
    assert client.calls[0]["workflow"] == "claims_intake"


def test_detected_warnings_travel_on_the_handshake(client, monkeypatch):
    """A binding whose denial would be swallowed must say so at install time."""
    class _SyncTool:
        name = "refund_payment"

        def func(self):
            return None

    class _Graph:
        tools = [_SyncTool()]

    adapter = LangGraphAdapter()
    adapter.patch(client, target=_Graph())
    assert any(
        "sync_tool_denial_swallowed:refund_payment" in w
        for w in client.calls[0]["silent_noop_warnings"]
    )


def test_a_failing_handshake_does_not_break_patch(monkeypatch):
    """The control plane being unreachable at import time must not stop the
    host application from starting."""
    class _ExplodingClient:
        def report_coverage(self, **kwargs):
            raise RuntimeError("control plane down")

    adapter = LangGraphAdapter()
    adapter.patch(_ExplodingClient())  # must not raise
