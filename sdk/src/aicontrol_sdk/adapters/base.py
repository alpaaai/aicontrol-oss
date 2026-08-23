"""FrameworkAdapter protocol — one adapter per supported agent framework."""
import logging
from typing import Any, Protocol

from aicontrol_sdk.intercept_client import InterceptClient
from aicontrol_sdk.noop_detection import detect_silent_noop

logger = logging.getLogger("aicontrol_sdk.adapters")


def sdk_version() -> str:
    """The installed aicontrol-sdk version, reported on the handshake so an
    operator can tell which build is bound to which agent."""
    try:
        from importlib.metadata import version

        return version("aicontrol-sdk")
    except Exception:
        return "unknown"


class WorkflowResolution:
    """Shared workflow resolution. Order (spec 3.2): the framework's own
    process name -> the workflow declared on the registered agent ->
    "unassigned".

    Every framework already carries a stable process name; capturing it is
    what makes an audit trail groupable by business process rather than by a
    stranger's uuid. Both attributes are class-level defaults so an adapter
    resolves correctly even before patch() has run.
    """

    _framework_workflow: str | None = None
    _declared_workflow: str | None = None

    def resolve_workflow(self) -> str:
        return self._framework_workflow or self._declared_workflow or "unassigned"


class CoverageReporting:
    """The install-time handshake every adapter sends at the end of patch().

    Without it, "the library was never installed" and "the library is
    installed and the hook never fires" look identical from the server: both
    are simply an agent with no traffic. `hook` names the exact framework
    callback this adapter bound, so an operator can see what is meant to be
    firing.
    """

    #: The framework callback this adapter binds. Reported verbatim.
    hook: str = "unknown"

    def report_coverage(self, client: Any, target: Any = None) -> None:
        """Fire-and-forget. Never raises: a governance library must not stop
        the host application from starting because the control plane was
        briefly unreachable at import time, and a silent-no-op detector must
        not either."""
        try:
            client.report_coverage(
                framework=self.name,
                hook=self.hook,
                sdk_version=sdk_version(),
                workflow=self.resolve_workflow(),
                agent_name=getattr(getattr(client, "_config", None), "agent_name", None),
                silent_noop_warnings=detect_silent_noop(self.name, target),
            )
        except Exception as exc:
            logger.warning("coverage_handshake_failed framework=%s error=%s", self.name, exc)


class FrameworkAdapter(Protocol):
    name: str

    def is_available(self) -> bool:
        """Whether this framework's package is importable in the current environment."""
        ...

    def patch(self, client: InterceptClient, workflow: str | None = None) -> None:
        """Wire this framework's tool-execution lifecycle to call
        client.intercept(). `workflow` names the business process the agent
        serves, used when the framework exposes no name of its own."""
        ...

    def resolve_workflow(self) -> str:
        """The business process this agent's calls belong to, or "unassigned"."""
        ...

    def extract_usage(self, response: Any) -> dict:
        """Pulls real per-LLM-call token usage off a raw framework response
        or message object (e.g. ModelResponse, LlmResponse, AssistantMessage).
        Called internally by the adapter's own usage-capture tap to feed the
        accumulator that the tool-execution hook reads from — not called
        directly by patch() or any external caller.

        Returns a dict with any subset of input_tokens/output_tokens keys, or
        {} if the object carries no usage. The capture point differs per
        framework: OpenAI Agents and Google ADK call this from a
        framework-invoked model-call hook (on_llm_end, after_model_callback).
        The Claude Agent SDK has no such hook — instead its adapter taps
        AssistantMessage instances off the message stream
        (ClaudeSDKClient.receive_messages / query()), the only place per-turn
        usage appears in that SDK. All three route through this same method
        and feed the same accumulate-then-drain-on-next-tool-call pattern.
        """
        ...
