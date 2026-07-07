"""SDK exceptions raised on non-allow decisions from AIControl."""
from typing import Optional


class PolicyDeniedError(Exception):
    """Raised when AIControl denies a tool call."""

    def __init__(self, reason: str, policy_name: Optional[str] = None):
        self.reason = reason
        self.policy_name = policy_name
        super().__init__(f"Tool call denied by policy: {reason}")


class ReviewPendingError(Exception):
    """Raised when AIControl requires human approval before proceeding."""

    def __init__(self, review_id: str):
        self.review_id = review_id
        super().__init__(f"Human review required. Review ID: {review_id}")


class AIControlUnavailableError(Exception):
    """Raised when AIControl cannot be reached and AICONTROL_FAIL_MODE is 'deny'."""

    def __init__(self, cause: Optional[BaseException] = None):
        self.cause = cause
        super().__init__(f"AIControl unavailable: {cause}")
