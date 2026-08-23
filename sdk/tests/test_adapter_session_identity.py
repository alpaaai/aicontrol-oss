"""Adapters must not fabricate a session id when the framework supplies one."""
import uuid

from aicontrol_sdk.adapters.crewai_adapter import CrewAIAdapter
from aicontrol_sdk.adapters.langgraph_adapter import LangGraphAdapter
from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def test_openai_prefers_group_id_over_generated():
    adapter = OpenAIAgentsSDKAdapter.__new__(OpenAIAgentsSDKAdapter)
    assert adapter.resolve_session_id(group_id="grp-123", trace_id="trc-9") == "grp-123"


def test_openai_falls_back_to_trace_id():
    adapter = OpenAIAgentsSDKAdapter.__new__(OpenAIAgentsSDKAdapter)
    assert adapter.resolve_session_id(group_id=None, trace_id="trc-9") == "trc-9"


def test_openai_generates_only_as_last_resort():
    adapter = OpenAIAgentsSDKAdapter.__new__(OpenAIAgentsSDKAdapter)
    assert _is_uuid(adapter.resolve_session_id(group_id=None, trace_id=None))


def test_openai_reads_the_ids_off_a_run_config():
    """The ids arrive on RunConfig, so the adapter has to be able to read them
    from one -- not only from keyword arguments a test hands it."""
    class _RunConfig:
        group_id = "grp-abc"
        trace_id = "trc-abc"

    adapter = OpenAIAgentsSDKAdapter.__new__(OpenAIAgentsSDKAdapter)
    assert adapter.session_id_from_run_config(_RunConfig()) == "grp-abc"


def test_openai_run_config_without_ids_still_yields_a_session():
    adapter = OpenAIAgentsSDKAdapter.__new__(OpenAIAgentsSDKAdapter)
    assert _is_uuid(adapter.session_id_from_run_config(None))


def test_langgraph_prefers_thread_id():
    adapter = LangGraphAdapter.__new__(LangGraphAdapter)
    assert adapter.resolve_session_id(thread_id="th-1", run_id="rn-2") == "th-1"


def test_langgraph_falls_back_to_run_id():
    adapter = LangGraphAdapter.__new__(LangGraphAdapter)
    assert adapter.resolve_session_id(thread_id=None, run_id="rn-2") == "rn-2"


def test_langgraph_generates_only_as_last_resort():
    adapter = LangGraphAdapter.__new__(LangGraphAdapter)
    assert _is_uuid(adapter.resolve_session_id(thread_id=None, run_id=None))


def test_langgraph_handler_uses_the_thread_id_from_the_run_config():
    """LangGraph passes the run config through to the callback, so the
    handler must take its session from there rather than from the id it was
    built with -- one handler serves many threads."""
    adapter = LangGraphAdapter.__new__(LangGraphAdapter)
    config = {"configurable": {"thread_id": "th-42"}}
    assert adapter.session_id_from_config(config) == "th-42"


def test_langgraph_run_config_without_thread_id_uses_the_run_id():
    adapter = LangGraphAdapter.__new__(LangGraphAdapter)
    assert adapter.session_id_from_config({}, run_id="rn-7") == "rn-7"


def test_crewai_session_id_differs_per_kickoff():
    adapter = CrewAIAdapter.__new__(CrewAIAdapter)
    first = adapter.new_session_id()
    second = adapter.new_session_id()
    assert first != second
    assert _is_uuid(first) and _is_uuid(second)


def test_crewai_session_id_is_stable_within_one_kickoff():
    """Every tool call in one crew run must share a session id, or the run is
    unreadable as a sequence."""
    adapter = CrewAIAdapter.__new__(CrewAIAdapter)
    adapter._session_id = None
    first = adapter.current_session_id()
    second = adapter.current_session_id()
    assert first == second


def test_crewai_new_kickoff_replaces_the_session_id():
    adapter = CrewAIAdapter.__new__(CrewAIAdapter)
    adapter._session_id = None
    first = adapter.current_session_id()
    adapter.start_kickoff()
    assert adapter.current_session_id() != first
