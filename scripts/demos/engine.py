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


async def _run_intercept(scenario: dict, token: str, mode: str) -> None:
    session_id = str(uuid.uuid4())
    print_scenario_header(scenario)

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


def _severity_line(severity_summary: dict) -> str:
    if not severity_summary:
        return "no findings"
    order = ["critical", "high", "medium", "low", "info"]
    parts = [f"{severity_summary[s]} {s}" for s in order if severity_summary.get(s)]
    return ", ".join(parts)


async def _cleanup_admission_scan_rows(scenario: dict) -> None:
    """Delete any mcp_servers rows this scenario's mcp_enroll steps created on a
    prior run, so re-running the demo doesn't accumulate duplicate rows (there's
    no UI for mcp_servers to dedupe from)."""
    from sqlalchemy import text
    from app.models.database import async_session_factory

    names = [step["name"] for step in scenario["steps"] if step["kind"] == "mcp_enroll"]
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM mcp_servers WHERE name = ANY(:names)"), {"names": names})
        await session.commit()


async def _run_admission_scan(scenario: dict, token: str, mode: str) -> None:
    await _cleanup_admission_scan_rows(scenario)

    print_scenario_header(scenario)

    results = []
    steps = scenario["steps"]

    async with httpx.AsyncClient() as client:
        for i, step in enumerate(steps, 1):
            console.print(f"[dim]Step {i} of {len(steps)}[/dim]")
            console.print(f"[bold]-> {step['label']}[/bold]")
            console.print(f"  [dim]{step['narrative']}[/dim]")

            if mode == "walkthrough":
                console.print("\n  [dim]Press ENTER to run...[/dim]", end="")
                input()

            start = time.time()

            if step["kind"] == "skill_scan":
                console.print(f"  [cyan]POST /admission-scans[/cyan]  target_ref={step['target_ref']}")
                resp = await client.post(
                    f"{API_BASE}/admission-scans",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"target_type": "skill", "target_ref": step["target_ref"], "scanners": ["skill_scanner"]},
                    timeout=30.0,
                )
                elapsed = (time.time() - start) * 1000
                data = resp.json()
                if resp.status_code != 201:
                    console.print(f"\n  [red]HTTP {resp.status_code}[/red]  {data}")
                    results.append({"step": i, "target": step["label"], "outcome": f"error {resp.status_code}", "ms": f"{elapsed:.0f}"})
                    console.print()
                    continue
                scan = data[0]
                severity_summary = scan["severity_summary"]
                findings_count = len(scan["findings"])
                is_blocked = bool(severity_summary.get("critical") or severity_summary.get("high"))
                color = "red" if is_blocked else "green"
                icon = "✗" if is_blocked else "✓"
                console.print(
                    f"\n  [{color}]{icon} {findings_count} finding(s)[/{color}]"
                    f"  [dim]{_severity_line(severity_summary)}  |  {elapsed:.0f}ms[/dim]"
                )
                for f in scan["findings"][:3]:
                    fcolor = {"critical": "red", "high": "red", "medium": "yellow", "low": "blue", "info": "dim"}.get(f["severity"], "white")
                    console.print(f"    [{fcolor}]{f['severity'].upper()}[/{fcolor}] {f['message']}  [dim]({f['rule_id']}{' @ ' + f['location'] if f.get('location') else ''})[/dim]")
                results.append({"step": i, "target": step["label"], "outcome": f"{findings_count} findings ({_severity_line(severity_summary)})", "ms": f"{elapsed:.0f}"})

            elif step["kind"] == "mcp_enroll":
                console.print(f"  [cyan]POST /mcp-servers[/cyan]  base_url={step['base_url']}")
                resp = await client.post(
                    f"{API_BASE}/mcp-servers",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"name": step["name"], "base_url": step["base_url"]},
                    timeout=90.0,
                )
                elapsed = (time.time() - start) * 1000
                data = resp.json()
                if resp.status_code != 201:
                    console.print(f"\n  [red]HTTP {resp.status_code}[/red]  {data}")
                    results.append({"step": i, "target": step["label"], "outcome": f"error {resp.status_code}", "ms": f"{elapsed:.0f}"})
                    console.print()
                    continue
                status = data["status"]
                color = "red" if status == "blocked" else "green"
                icon = "✗" if status == "blocked" else "✓"
                console.print(f"\n  [{color}]{icon} STATUS: {status.upper()}[/{color}]  [dim]{elapsed:.0f}ms[/dim]")
                results.append({"step": i, "target": step["label"], "outcome": f"status={status}", "ms": f"{elapsed:.0f}"})

            console.print(f"  [italic dim]{step['insight']}[/italic dim]")

            if mode == "walkthrough":
                console.print()
                time.sleep(0.4)
            else:
                time.sleep(0.2)

    console.print()
    table = Table(title="Session Summary", box=box.SIMPLE_HEAVY)
    table.add_column("Step", style="dim", width=6)
    table.add_column("Target", style="cyan")
    table.add_column("Outcome")
    table.add_column("ms", style="dim", width=6)
    for r in results:
        table.add_row(str(r["step"]), r["target"], r["outcome"], r["ms"])
    console.print(table)
    console.print()
    console.print(f"[dim]Dashboard (skill scans only): http://localhost:3000/admission-scans[/dim]")
    console.print()


GATEWAY_BASE = os.getenv("AICONTROL_GATEWAY_URL", "http://localhost:8002")


async def _setup_mcp_gateway(scenario: dict, token: str, client: httpx.AsyncClient) -> str:
    """Register the downstream server and approve its tools. Returns server_id."""
    from sqlalchemy import text
    from app.models.database import async_session_factory

    server_name = scenario["server_name"]

    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM mcp_servers WHERE name = :name"), {"name": server_name})
        await session.commit()

    resp = await client.post(
        f"{API_BASE}/mcp-servers",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": server_name, "base_url": scenario["downstream_base_url"]},
        timeout=30.0,
    )
    resp.raise_for_status()
    server_id = resp.json()["id"]

    async with async_session_factory() as session:
        await session.execute(
            text("INSERT INTO mcp_servers (id, name, base_url, approved_tools) "
                 "VALUES (:id, :name, :base_url, CAST(:tools AS jsonb)) "
                 "ON CONFLICT (id) DO UPDATE SET approved_tools = CAST(:tools AS jsonb)"),
            {"id": server_id, "name": server_name, "base_url": scenario["downstream_base_url"],
             "tools": json.dumps(scenario["approved_tools"])},
        )
        await session.commit()

    return server_id


async def _run_mcp_gateway(scenario: dict, token: str, mode: str) -> None:
    print_scenario_header(scenario)

    async with httpx.AsyncClient() as client:
        console.print("[dim]Registering downstream server and approving tools...[/dim]")
        server_id = await _setup_mcp_gateway(scenario, token, client)
        console.print(f"[dim]Server registered: {server_id}[/dim]")
        console.print()

        results = []
        steps = scenario["steps"]

        for i, step in enumerate(steps, 1):
            console.print(f"[dim]Step {i} of {len(steps)}[/dim]")
            console.print(f"[bold]-> {step['label']}[/bold]")
            console.print(f"  [dim]{step['narrative']}[/dim]")

            if mode == "walkthrough":
                console.print("\n  [dim]Press ENTER to send...[/dim]", end="")
                input()

            url = f"{GATEWAY_BASE}/mcp/{server_id}/{step['method']}"
            console.print(f"  [cyan]POST /{step['method']}[/cyan]  {json.dumps(step['body'])}")

            start = time.time()
            resp = await client.post(url, json=step["body"], timeout=15.0)
            elapsed = (time.time() - start) * 1000
            data = resp.json()

            if step["method"] == "tools/list":
                tools = [t["name"] for t in data.get("tools", [])]
                console.print(f"\n  [green]✓ tools visible to agent: {tools}[/green]  [dim]{elapsed:.0f}ms[/dim]")
                results.append({"step": i, "call": step["label"], "outcome": f"visible={tools}", "ms": f"{elapsed:.0f}"})
            else:
                is_error = data.get("isError", False)
                text_out = ""
                for c in data.get("content", []):
                    if c.get("type") == "text":
                        text_out = c["text"]
                        break
                color = "red" if is_error else "green"
                icon = "✗" if is_error else "✓"
                console.print(f"\n  [{color}]{icon} {text_out}[/{color}]  [dim]{elapsed:.0f}ms[/dim]")
                results.append({"step": i, "call": step["label"], "outcome": text_out, "ms": f"{elapsed:.0f}"})

            console.print(f"  [italic dim]{step['insight']}[/italic dim]")

            if mode == "walkthrough":
                console.print()
                time.sleep(0.4)
            else:
                time.sleep(0.2)

    console.print()
    table = Table(title="Session Summary", box=box.SIMPLE_HEAVY)
    table.add_column("Step", style="dim", width=6)
    table.add_column("Call", style="cyan")
    table.add_column("Outcome")
    table.add_column("ms", style="dim", width=6)
    for r in results:
        table.add_row(str(r["step"]), r["call"], r["outcome"], r["ms"])
    console.print(table)
    console.print()
    console.print(f"[dim]Dashboard (audit trail, agent_name=mcp-gateway:{scenario['server_name']}): http://localhost:3000/audit-log[/dim]")
    console.print()


def dispatch(name: str, token: str, mode: str = "walkthrough") -> None:
    scenario = SCENARIOS[name]
    kind = scenario["kind"]
    if kind == "intercept":
        asyncio.run(_run_intercept(scenario, token, mode))
    elif kind == "admission_scan":
        asyncio.run(_run_admission_scan(scenario, token, mode))
    elif kind == "mcp_gateway":
        asyncio.run(_run_mcp_gateway(scenario, token, mode))
    else:
        raise ValueError(f"Unknown demo kind: {kind!r}")
