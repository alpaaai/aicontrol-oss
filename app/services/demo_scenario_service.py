"""Reads the canonical demo scenario JSON files. Pure file I/O, no caching --
the files are tiny and read once per request, which keeps a policy-content
edit visible without an API restart."""
import json
from pathlib import Path

from app.models.demo_scenario_schemas import DemoScenarioDetail, DemoScenarioSummary

SCENARIOS_DIR = Path(__file__).parent.parent / "demo_scenarios"


def all_scenario_ids() -> list[str]:
    return sorted(p.stem for p in SCENARIOS_DIR.glob("*.json"))


def get_scenario(scenario_id: str) -> DemoScenarioDetail:
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.exists():
        raise KeyError(scenario_id)
    with path.open() as f:
        return DemoScenarioDetail.model_validate(json.load(f))


def list_scenarios() -> list[DemoScenarioSummary]:
    return [
        DemoScenarioSummary.model_validate(get_scenario(sid).model_dump())
        for sid in all_scenario_ids()
    ]
