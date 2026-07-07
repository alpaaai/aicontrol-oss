import pytest


def test_policy_denied_error_carries_reason_and_policy_name():
    from aicontrol_sdk.exceptions import PolicyDeniedError

    err = PolicyDeniedError(reason="tool_denylisted", policy_name="block_dangerous_tools")
    assert err.reason == "tool_denylisted"
    assert err.policy_name == "block_dangerous_tools"
    assert "tool_denylisted" in str(err)


def test_review_pending_error_carries_review_id():
    from aicontrol_sdk.exceptions import ReviewPendingError

    err = ReviewPendingError(review_id="abc-123")
    assert err.review_id == "abc-123"
    assert "abc-123" in str(err)


def test_aicontrol_unavailable_error_carries_cause():
    from aicontrol_sdk.exceptions import AIControlUnavailableError

    cause = ConnectionError("boom")
    err = AIControlUnavailableError(cause=cause)
    assert err.cause is cause
