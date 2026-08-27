"""Shared rendering and execution engine for AIControl demo scenarios.

Each scenario in scripts/demos/scenarios.py declares a "kind"
(intercept | admission_scan | mcp_gateway). dispatch() routes to the
matching _run_* function below. The pure helpers in this section have no
I/O and are unit tested directly; the _run_* functions call out to a real
AIControl API over httpx and are tested with a mocked AsyncClient.
"""
import asyncio
import json
import os
import time
import uuid
from typing import Optional

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from scripts.demos.scenarios import SCENARIOS

console = Console()

API_BASE = os.getenv("AICONTROL_API_URL", "http://localhost:8001")

_DECISION_STYLE = {
    "allow": ("green", "✓"),
    "deny": ("red", "✗"),
    "review": ("yellow", "⚑"),
}


def decision_style(decision: str) -> tuple[str, str]:
    return _DECISION_STYLE.get(decision, ("white", "?"))


def v2_badge(call: dict) -> str:
    feature = call.get("v2_feature")
    if not feature:
        return ""
    return f"  [bold magenta][V2: {feature.upper()}][/bold magenta]"


def select_deny_detail(scenario: dict, data: dict) -> Optional[str]:
    field = scenario.get("deny_detail_field", "reason")
    return data.get(field) or None


def build_intercept_payload(scenario: dict, session_id: str, call: dict, sequence_number: int) -> dict:
    return {
        "session_id": session_id,
        "agent_id": scenario["agent_id"],
        "agent_name": scenario["agent_name"],
        "tool_name": call["tool_name"],
        "tool_parameters": call["tool_parameters"],
        "sequence_number": sequence_number,
    }


def print_scenario_header(scenario: dict) -> None:
    console.print()
    console.print(Panel(
        f"[bold white]{scenario['name']}[/bold white]\n"
        f"[white]{scenario['description']}[/white]",
        style="blue", box=box.ROUNDED,
    ))
    console.print()


async def _call_coverage_handshake(scenario: dict, token: str) -> None:
    """Register agent framework and hook coverage before running tool calls."""
    coverage_payload = {
        "framework": scenario.get("framework", "unknown"),
        "hook": scenario.get("hook", "aicontrol-sdk"),
        "sdk_version": scenario.get("sdk_version", "1.0.0"),
        "workflow": scenario.get("workflow", "unassigned"),
        "agent_name": scenario["agent_name"],
        "silent_noop_warnings": [],
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API_BASE}/agents/{scenario['agent_id']}/coverage",
                headers={"Authorization": f"Bearer {token}"},
                json=coverage_payload,
                timeout=10.0,
            )
        if resp.status_code == 200:
            console.print("[dim]✓ Coverage handshake sent[/dim]")
        else:
            console.print(f"[yellow]⚠ Coverage handshake returned {resp.status_code}[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠ Coverage handshake failed: {e}[/yellow]")


async def _run_intercept(scenario: dict, token: str, mode: str) -> None:
    session_id = str(uuid.uuid4())
    print_scenario_header(scenario)

    await _call_coverage_handshake(scenario, token)
    console.print()

    results = []
    tool_calls = scenario["tool_calls"]

    for i, call in enumerate(tool_calls, 1):
        console.print(f"[dim]Step {i} of {len(tool_calls)}[/dim]")
        console.print(f"[bold]→ {call['label']}[/bold]")
        console.print(f"  Tool: [cyan]{call['tool_name']}[/cyan]")
        console.print(f"  Params: [dim]{json.dumps(call['tool_parameters'])}[/dim]")

        if mode == "walkthrough":
            console.print("\n  [dim]Press ENTER to send...[/dim]", end="")
            input()

        start = time.time()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API_BASE}/intercept",
                headers={"Authorization": f"Bearer {token}"},
                json=build_intercept_payload(scenario, session_id, call, i),
                timeout=10.0,
            )
        elapsed = (time.time() - start) * 1000

        data = resp.json()
        decision = data.get("decision", "error")
        reason = data.get("reason", "—")
        color, icon = decision_style(decision)
        badge = v2_badge(call)

        console.print(
            f"\n  [{color}]{icon} DECISION: {decision.upper()}[/{color}]{badge}"
            f"  [dim]reason: {reason}  |  {elapsed:.0f}ms[/dim]"
        )
        if decision == "deny":
            detail = select_deny_detail(scenario, data)
            if detail:
                color_name = scenario.get("deny_detail_color", "red")
                indent = scenario.get("deny_detail_indent", "  ")
                console.print(f"{indent}[{color_name}]Policy: {detail}[/{color_name}]")
        if decision == "review":
            note = call.get("review_note")
            if note:
                console.print(f"    [yellow]⚑ {note}[/yellow]")

        results.append({
            "step": i,
            "tool": call["tool_name"],
            "decision": decision,
            "reason": reason,
            "ms": f"{elapsed:.0f}",
        })

        if mode == "walkthrough":
            console.print()
            time.sleep(0.5)
        else:
            time.sleep(0.3)

    console.print()
    table = Table(title="Session Summary", box=box.SIMPLE_HEAVY)
    table.add_column("Step", style="dim", width=6)
    table.add_column("Tool", style="cyan")
    table.add_column("Decision", width=10)
    table.add_column("Reason", style="dim")
    table.add_column("ms", style="dim", width=6)
    for r in results:
        color, _ = decision_style(r["decision"])
        table.add_row(str(r["step"]), r["tool"], f"[{color}]{r['decision'].upper()}[/{color}]", r["reason"] or "—", r["ms"])
    console.print(table)
    console.print()
    console.print(f"[dim]Dashboard: http://localhost:3000[/dim]")
    console.print()


def dispatch(name: str, token: str, mode: str = "walkthrough") -> None:
    scenario = SCENARIOS[name]
    kind = scenario["kind"]
    if kind == "intercept":
        asyncio.run(_run_intercept(scenario, token, mode))
    else:
        raise ValueError(f"Unknown demo kind: {kind!r}")
