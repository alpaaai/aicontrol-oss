"""Every adapter resolves a workflow, and falls back predictably."""
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


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS, ids=lambda c: c.__name__)
def test_every_adapter_exposes_resolve_workflow(adapter_cls):
    assert hasattr(adapter_cls, "resolve_workflow")


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS, ids=lambda c: c.__name__)
def test_unresolvable_workflow_falls_back_to_unassigned(adapter_cls):
    adapter = adapter_cls.__new__(adapter_cls)
    adapter._declared_workflow = None
    adapter._framework_workflow = None
    assert adapter.resolve_workflow() == "unassigned"


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS, ids=lambda c: c.__name__)
def test_declared_workflow_used_when_framework_has_none(adapter_cls):
    adapter = adapter_cls.__new__(adapter_cls)
    adapter._declared_workflow = "claims_intake"
    adapter._framework_workflow = None
    assert adapter.resolve_workflow() == "claims_intake"


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS, ids=lambda c: c.__name__)
def test_framework_name_wins_over_declared(adapter_cls):
    adapter = adapter_cls.__new__(adapter_cls)
    adapter._declared_workflow = "declared"
    adapter._framework_workflow = "from_framework"
    assert adapter.resolve_workflow() == "from_framework"


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS, ids=lambda c: c.__name__)
def test_resolve_workflow_needs_no_instance_state(adapter_cls):
    """A fresh instance must resolve without patch() having run -- the class
    defaults carry it, so a caller that never declares one still gets
    "unassigned" rather than an AttributeError on the intercept path."""
    adapter = adapter_cls.__new__(adapter_cls)
    assert adapter.resolve_workflow() == "unassigned"


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS, ids=lambda c: c.__name__)
def test_patch_stores_the_declared_workflow(adapter_cls, stub_client, monkeypatch):
    """patch(client, workflow=...) is how an integrator names the business
    process when their framework has no name of its own."""
    adapter = adapter_cls()
    _neutralise_framework_patching(adapter, monkeypatch)
    adapter.patch(stub_client, workflow="claims_intake")
    assert adapter._declared_workflow == "claims_intake"


def _neutralise_framework_patching(adapter, monkeypatch):
    """Four of the five adapters import their framework inside patch(). Skip
    straight past that -- this test is about workflow storage, not wiring."""
    import sys
    from types import ModuleType, SimpleNamespace

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


@pytest.fixture
def stub_client():
    class _StubClient:
        def __init__(self):
            self.coverage_calls = []

        def report_coverage(self, **kwargs):
            self.coverage_calls.append(kwargs)

    return _StubClient()
