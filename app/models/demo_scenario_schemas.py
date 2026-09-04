"""Pydantic shapes for the canonical demo scenario JSON files under
app/demo_scenarios/*.json — the single source of truth the CLI and the
frontend both fetch from over GET /demo/scenarios[/​{id}]."""
from typing import Literal

from pydantic import BaseModel

Decision = Literal["allow", "deny", "review"]


class DemoStep(BaseModel):
    tool_name: str
    tool_parameters: dict
    label: str
    narrative: str
    expected: Decision
    decision_narratives: dict[str, str]


class DemoScenarioSummary(BaseModel):
    id: str
    industry: str
    name: str
    description: str
    incident_headline: str


class DemoScenarioDetail(BaseModel):
    id: str
    industry: str
    name: str
    description: str
    incident_headline: str
    agent_id: str
    agent_name: str
    owner: str
    workflow: str
    approved_tools: list[str]
    closing_line: str
    steps: list[DemoStep]
