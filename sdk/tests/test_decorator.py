import itertools
import uuid
import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.intercept = AsyncMock(return_value={"decision": "allow", "reason": "default_allow", "audit_event_id": "e1"})
    return client


@pytest.mark.asyncio
async def test_control_calls_intercept_before_running_function(mock_client):
    from aicontrol_sdk.decorator import control

    @control("query_database", client=mock_client)
    async def query_database(table: str):
        return f"rows from {table}"

    result = await query_database(table="customers")

    assert result == "rows from customers"
    mock_client.intercept.assert_awaited_once()
    call_kwargs = mock_client.intercept.call_args.kwargs
    assert call_kwargs["tool_name"] == "query_database"
    assert call_kwargs["tool_parameters"] == {"table": "customers"}


@pytest.mark.asyncio
async def test_control_increments_sequence_number_per_call(mock_client):
    from aicontrol_sdk.decorator import control

    @control("query_database", client=mock_client)
    async def query_database(table: str):
        return "ok"

    session_id = str(uuid.uuid4())
    await query_database(table="a", session_id=session_id)
    await query_database(table="b", session_id=session_id)

    seqs = [c.kwargs["sequence_number"] for c in mock_client.intercept.call_args_list]
    assert seqs == [1, 2]


@pytest.mark.asyncio
async def test_control_does_not_run_function_on_deny(mock_client):
    from aicontrol_sdk.decorator import control
    from aicontrol_sdk.exceptions import PolicyDeniedError

    mock_client.intercept = AsyncMock(side_effect=PolicyDeniedError(reason="tool_denylisted"))
    ran = {"called": False}

    @control("dangerous_tool", client=mock_client)
    async def dangerous_tool():
        ran["called"] = True
        return "should not happen"

    with pytest.raises(PolicyDeniedError):
        await dangerous_tool()

    assert ran["called"] is False


@pytest.mark.asyncio
async def test_control_wraps_sync_function(mock_client):
    from aicontrol_sdk.decorator import control

    @control("sync_tool", client=mock_client)
    def sync_tool(x: int):
        return x * 2

    result = await sync_tool(x=5)
    assert result == 10


@pytest.mark.asyncio
async def test_control_captures_positional_arguments(mock_client):
    """A tool called with positional arguments must still have those arguments
    appear in tool_parameters sent to the backend -- today only kwargs are
    captured, so a policy inspecting tool_parameters sees an incomplete/empty
    dict while the real call executes with the real (unseen) arguments."""
    from aicontrol_sdk.decorator import control

    @control("query_database", client=mock_client)
    async def query_database(table: str, limit: int = 100):
        return f"{table}:{limit}"

    await query_database("customers", 50)

    call_kwargs = mock_client.intercept.call_args.kwargs
    assert call_kwargs["tool_parameters"] == {"table": "customers", "limit": 50}
