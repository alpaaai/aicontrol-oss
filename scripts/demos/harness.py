"""Shared demo harness (spec 6.2): a real agent on the OpenAI Agents SDK,
wired through our real adapter, making genuine tool calls that are governed
by a real in-process /intercept call. Only the LLM is mockable -- fixture
mode replays a canned transcript instead of calling OpenAI; enforcement is
identical in both modes.

D15 (22 Aug 2026): all three demos run on the OpenAI Agents SDK -- see
plans/v3/2026-08-22-v3-phases-4-7-surface.md task 6.1.

The harness owns registering the demo agent, issuing its token, wiring the
adapter, and selecting fixture-vs-live LLM. Each scenario module under
scripts/demos/fixtures/<name>.json supplies only its scenario: the agent
identity, its tools, and the beats (a beat is a single Runner.run() -- see
_run_beat for why a beat, not the whole scenario, is the unit of a run).
"""
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

from httpx import ASGITransport
from sqlalchemy import text

from agents import Agent, RunConfig, Runner
from agents.items import ModelResponse, ResponseFunctionToolCall, ResponseOutputMessage
from agents.models.interface import Model
from agents.tool import FunctionTool
from agents.usage import Usage
from openai.types.responses.response_output_text import ResponseOutputText

from aicontrol_sdk.adapters.openai_agents_sdk import OpenAIAgentsSDKAdapter
from aicontrol_sdk.config import Config
from aicontrol_sdk.exceptions import PolicyDeniedError, ReviewPendingError, UnknownDecisionError
from aicontrol_sdk.intercept_client import InterceptClient

from app.core import license_gate
from app.core.auth import create_token, hash_token
from app.main import app
from app.models.database import async_session_factory

logging.getLogger("aicontrol_sdk").setLevel(logging.CRITICAL)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(scenario: str) -> dict:
    """Read the static scenario transcript. Pure file read -- two calls for
    the same scenario always return equal (deep-equal) dicts."""
    path = FIXTURES_DIR / f"{scenario}.json"
    with path.open() as f:
        return json.load(f)


class FixtureModel(Model):
    """Replays one beat's scripted tool calls, then ends the turn with a
    plain text message. No network call is ever made -- fixture mode needs
    no API key."""

    def __init__(self, steps: list[dict]):
        self._steps = list(steps)
        self._i = 0

    async def get_response(
        self, system_instructions, input, model_settings, tools, output_schema,
        handoffs, tracing, *, previous_response_id, conversation_id, prompt,
    ) -> ModelResponse:
        if self._i < len(self._steps):
            step = self._steps[self._i]
            self._i += 1
            call = ResponseFunctionToolCall(
                arguments=json.dumps(step["args"]),
                call_id=f"call_{self._i}",
                name=step["tool"],
                type="function_call",
                id=f"fc_{self._i}",
                status="completed",
            )
            return ModelResponse(output=[call], usage=Usage(), response_id=f"fixture_{self._i}")
        message = ResponseOutputMessage(
            id="fixture_final",
            role="assistant",
            status="completed",
            type="message",
            content=[ResponseOutputText(text="done", type="output_text", annotations=[])],
        )
        return ModelResponse(output=[message], usage=Usage(), response_id="fixture_final")

    def stream_response(self, *args, **kwargs):
        raise NotImplementedError("demo harness runs fixture mode non-streamed only")


def _make_tool(name: str, description: str, canned_result: Any) -> FunctionTool:
    """A generic passthrough tool: real FunctionTool object, recognized and
    dispatched by the real Runner, returning a canned realistic result. The
    demo does not need real business logic behind these calls -- only that
    the call reaches on_tool_start with real arguments, which is what the
    governance decision is made against."""

    async def on_invoke_tool(ctx, args_json: str) -> Any:
        return canned_result if canned_result is not None else "ok"

    return FunctionTool(
        name=name,
        description=description,
        params_json_schema={"type": "object", "properties": {}, "additionalProperties": True},
        on_invoke_tool=on_invoke_tool,
        strict_json_schema=False,
    )


class RecordingInterceptClient(InterceptClient):
    """An InterceptClient that keeps the full /intercept response for every
    call, including deny/review -- the SDK exceptions PolicyDeniedError and
    ReviewPendingError only carry a reason/review_id, not the audit_event_id
    or policy_name the demo tests need, so this re-implements the same
    decide-then-raise contract while keeping everything it saw."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.results: list[dict] = []

    async def intercept(
        self, tool_name, tool_parameters, session_id, sequence_number,
        workflow: str = "unassigned", input_tokens=None, output_tokens=None, cost_usd=None,
    ) -> dict:
        body: dict[str, Any] = {
            "session_id": session_id,
            "agent_id": self._config.agent_id,
            "agent_name": self._config.agent_name,
            "tool_name": tool_name,
            "tool_parameters": tool_parameters,
            "sequence_number": sequence_number,
            "workflow": workflow,
        }
        if input_tokens is not None:
            body["input_tokens"] = input_tokens
        if output_tokens is not None:
            body["output_tokens"] = output_tokens
        if cost_usd is not None:
            body["cost_usd"] = cost_usd

        response = await self._client.post(
            "/intercept",
            headers={"Authorization": f"Bearer {self._config.token}"},
            json=body,
        )
        response.raise_for_status()
        result = response.json()
        self.results.append({**result, "tool_name": tool_name, "workflow": workflow})

        decision = result["decision"]
        if decision == "allow":
            return result
        if decision == "deny":
            raise PolicyDeniedError(reason=result["reason"], policy_name=result.get("policy_name"))
        if decision == "review":
            await self._wait_for_review_visible(result["review_id"])
            raise ReviewPendingError(review_id=result["review_id"])
        raise UnknownDecisionError(decision=decision)

    async def _wait_for_review_visible(self, review_id: str, attempts: int = 40) -> None:
        """The review row is written on the request's own DB session, which
        (per the project's known get_db pitfall) commits in dependency
        teardown -- after the response body is already back in our hands.
        A caller reading the row through a *different* connection right
        after run() returns can race that commit. Poll a fresh session
        until it's visible, so nothing downstream has to know about this."""
        from app.models.schemas import HITLReview
        from sqlalchemy import select

        for _ in range(attempts):
            async with async_session_factory() as session:
                found = (await session.execute(
                    select(HITLReview.id).where(HITLReview.id == uuid.UUID(str(review_id)))
                )).scalar_one_or_none()
            if found is not None:
                return
            import asyncio
            await asyncio.sleep(0.02)


class DemoHarness:
    def __init__(self, scenario: str, live: bool = False):
        self.scenario_name = scenario
        self.live = live
        self.llm_mode = "live" if live else "fixture"
        self.intercept_is_live = True
        self.adapter = OpenAIAgentsSDKAdapter()
        self.session_id = str(uuid.uuid4())
        self.expected_group_id = self.session_id
        self.skipped_beats: list[str] = []

        self.spec = load_fixture(scenario)
        self._client: Optional[RecordingInterceptClient] = None
        self._registered = False

    async def _register_agent_and_token(self) -> None:
        if self._registered:
            return
        agent_id = self.spec["agent_id"]
        agent_name = self.spec["agent_name"]

        token = create_token(role="agent", description=f"demo-harness:{self.scenario_name}")
        token_hash = hash_token(token)

        async with async_session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO agents (id, name, owner, status, approved_tools)
                    VALUES (CAST(:id AS uuid), :name, :owner, 'active', CAST('[]' AS jsonb))
                    ON CONFLICT (id) DO NOTHING
                """),
                {"id": agent_id, "name": agent_name, "owner": self.spec.get("owner", "demo")},
            )
            await session.execute(
                text("""
                    INSERT INTO api_tokens (id, token_hash, role, description, agent_id, revoked)
                    VALUES (gen_random_uuid(), :hash, 'agent', :desc, CAST(:agent_id AS uuid), false)
                """),
                {"hash": token_hash, "desc": f"demo-harness:{self.scenario_name}", "agent_id": agent_id},
            )
            await session.commit()

        config = Config(url="http://demo", token=token, agent_id=agent_id, agent_name=agent_name)
        self._client = RecordingInterceptClient(config=config, transport=ASGITransport(app=app))
        self._registered = True

    def _tools_for_beat(self, beat: dict) -> list[FunctionTool]:
        tools = {}
        for step in beat["steps"]:
            name = step["tool"]
            tools[name] = _make_tool(
                name=name,
                description=self.spec["tools"].get(name, name),
                canned_result=step.get("result"),
            )
        return list(tools.values())

    async def _call_coverage_handshake(self) -> None:
        """Register agent framework and hook coverage with the API."""
        from httpx import AsyncClient

        coverage_payload = {
            "framework": self.spec.get("framework", "openai-agents-sdk"),
            "hook": self.spec.get("hook", "aicontrol-sdk"),
            "sdk_version": self.spec.get("sdk_version", "1.0.0"),
            "workflow": self.spec.get("workflow", "unassigned"),
            "agent_name": self.spec["agent_name"],
            "silent_noop_warnings": [],
        }
        try:
            async with AsyncClient(transport=ASGITransport(app=app)) as client:
                resp = await client.post(
                    f"/agents/{self.spec['agent_id']}/coverage",
                    headers={"Authorization": f"Bearer {self._client._config.token}"},
                    json=coverage_payload,
                    timeout=10.0,
                )
            if resp.status_code != 200:
                print(f"[warning] Coverage handshake returned {resp.status_code}")
        except Exception as e:
            print(f"[warning] Coverage handshake failed: {e}")

    async def _run_beat(self, beat: dict) -> None:
        """One beat == one Runner.run(). A deny/review raises from
        on_tool_start and aborts the run before the tool executes (the
        adapter's own documented contract) -- so a beat that contains both
        an allowed setup call and a blocked call is exactly one run that
        ends early, and a beat whose every call is allowed runs to
        completion and produces a final message."""
        model = FixtureModel(beat["steps"]) if not self.live else None
        agent = Agent(
            name=self.spec["agent_name"],
            instructions=beat.get("narrative", ""),
            tools=self._tools_for_beat(beat),
            model=model,
        )
        run_config = RunConfig(group_id=self.session_id, workflow_name=self.spec["workflow"])
        try:
            await Runner.run(agent, beat.get("narrative", "proceed"), run_config=run_config)
        except (PolicyDeniedError, ReviewPendingError):
            pass
        except Exception as exc:
            # The Agents SDK's own tool-execution loop catches any exception
            # from on_tool_start and re-raises it wrapped in UserError (see
            # agents/run_internal/tool_execution.py) unless it's already an
            # AgentsException -- so the real PolicyDeniedError/ReviewPendingError
            # this adapter raises to abort a run arrives here as __cause__,
            # not as the exception type itself.
            if isinstance(exc.__cause__, (PolicyDeniedError, ReviewPendingError)):
                pass
            else:
                raise

    async def run(self, mode: str = "fast") -> list[dict]:
        await self._register_agent_and_token()
        await self._call_coverage_handshake()
        self.adapter.patch(self._client, workflow=self.spec["workflow"])

        for beat in self.spec["beats"]:
            requires = beat.get("requires_license")
            if requires and not license_gate.has_enterprise_license():
                self.skipped_beats.append(f"{requires}:requires_enterprise_license")
                continue
            await self._run_beat(beat)

        return self._client.results

    async def approve(self, review_id, approver: str) -> dict:
        """The business beat isn't the hold -- it's the hold plus the
        approval plus the approver's name on the record. Cedar re-evaluates
        the same policy on any future call regardless of review status, so
        "the payment proceeds" is a fact about the HITLReview row, not a
        second /intercept decision."""
        from datetime import datetime, timezone

        from app.models.schemas import HITLReview
        from sqlalchemy import select

        async with async_session_factory() as session:
            review = (await session.execute(
                select(HITLReview).where(HITLReview.id == uuid.UUID(str(review_id)))
            )).scalar_one()
            review.status = "approved"
            review.reviewer = approver
            review.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.commit()

        return {"decision": "allow", "review_id": str(review_id), "approver": approver}
