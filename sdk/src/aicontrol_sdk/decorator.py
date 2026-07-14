"""@control decorator — framework-agnostic governance for any Python callable."""
import functools
import inspect
import itertools
import uuid
from typing import Any, Callable, Optional

from aicontrol_sdk.intercept_client import InterceptClient

_default_client: Optional[InterceptClient] = None
_default_session_id = str(uuid.uuid4())
_session_counters: dict[str, itertools.count] = {}


def _get_default_client() -> InterceptClient:
    global _default_client
    if _default_client is None:
        from aicontrol_sdk.config import Config
        _default_client = InterceptClient(config=Config.from_env())
    return _default_client


def control(tool_name: str, client: Optional[InterceptClient] = None) -> Callable:
    """Wrap a sync or async callable so every call is intercepted by AIControl first.

    Accepts optional session_id/sequence_number kwargs (stripped before the
    wrapped function runs); session_id defaults to a per-process id and
    sequence_number auto-increments per session if not supplied.
    """

    def decorator(func: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            session_id = kwargs.pop("session_id", _default_session_id)
            sequence_number = kwargs.pop("sequence_number", None)
            if sequence_number is None:
                counter = _session_counters.setdefault(session_id, itertools.count(1))
                sequence_number = next(counter)

            bound = inspect.signature(func).bind(*args, **kwargs)
            bound.apply_defaults()
            tool_parameters = dict(bound.arguments)

            active_client = client or _get_default_client()
            await active_client.intercept(
                tool_name=tool_name,
                tool_parameters=tool_parameters,
                session_id=session_id,
                sequence_number=sequence_number,
            )

            if is_async:
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        return wrapper

    return decorator
