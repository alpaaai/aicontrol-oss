"""Bind-time detection of configurations where the check never fires."""
from aicontrol_sdk.noop_detection import detect_silent_noop


class _FakeAnthropicOptions:
    def __init__(self, can_use_tool=None, allowed_tools=None):
        self.can_use_tool = can_use_tool
        self.allowed_tools = allowed_tools


def test_allowed_tools_shadowing_can_use_tool_is_flagged():
    target = _FakeAnthropicOptions(can_use_tool=lambda *_: None, allowed_tools=["read_file"])
    warnings = detect_silent_noop("anthropic", target)
    assert any("allowed_tools_shadows_can_use_tool" in w for w in warnings)


def test_can_use_tool_alone_is_clean():
    target = _FakeAnthropicOptions(can_use_tool=lambda *_: None, allowed_tools=None)
    assert detect_silent_noop("anthropic", target) == []


def test_allowed_tools_alone_is_clean():
    """Without a can_use_tool callback there is nothing for allowed_tools to
    shadow -- this adapter governs through a PreToolUse hook."""
    target = _FakeAnthropicOptions(can_use_tool=None, allowed_tools=["read_file"])
    assert detect_silent_noop("anthropic", target) == []


class _FakeTool:
    def __init__(self, name, is_function_tool=True):
        self.name = name
        if is_function_tool:
            self.__aicontrol_function_tool__ = True


class _FakeOpenAIAgent:
    def __init__(self, tools):
        self.tools = tools


def test_openai_non_function_tool_is_flagged():
    agent = _FakeOpenAIAgent([_FakeTool("safe"), _FakeTool("unguarded", is_function_tool=False)])
    warnings = detect_silent_noop("openai_agents", agent)
    assert any("unguarded" in w for w in warnings)


def test_openai_all_function_tools_is_clean():
    agent = _FakeOpenAIAgent([_FakeTool("a"), _FakeTool("b")])
    assert detect_silent_noop("openai_agents", agent) == []


def test_openai_target_without_tools_is_clean():
    """patch() is handed the Runner, not an agent, in the common case."""
    assert detect_silent_noop("openai_agents", object()) == []


class _SyncTool:
    name = "refund_payment"

    def func(self):
        return None


class _AsyncTool:
    name = "read_record"

    async def func(self):
        return None


class _FakeGraph:
    def __init__(self, tools):
        self.tools = tools


def test_langgraph_sync_tool_is_flagged_by_name():
    warnings = detect_silent_noop("langgraph", _FakeGraph([_SyncTool(), _AsyncTool()]))
    assert any("sync_tool_denial_swallowed:refund_payment" in w for w in warnings)
    assert not any("read_record" in w for w in warnings)


def test_langgraph_all_async_tools_is_clean():
    assert detect_silent_noop("langgraph", _FakeGraph([_AsyncTool()])) == []


def test_unknown_framework_returns_no_warnings():
    assert detect_silent_noop("crewai", object()) == []


def test_detection_never_raises_on_a_hostile_target():
    """This runs at import time in the host application. A detector that
    raises would take down the app it is supposed to be governing."""
    class _Exploding:
        @property
        def tools(self):
            raise RuntimeError("boom")

    assert detect_silent_noop("langgraph", _Exploding()) == []
    assert detect_silent_noop("openai_agents", _Exploding()) == []
