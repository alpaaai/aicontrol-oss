#!/usr/bin/env python3
"""
AIControl Demo Runner — runs a real agent through the shared demo harness.
Usage: python scripts/demos/run_demo.py --scenario insurance --mode fast
       python scripts/demos/run_demo.py --scenario insurance --live
"""
import argparse
import asyncio
import os
import sys
import time

_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from scripts.demos.harness import DemoHarness

SCENARIO_NAMES = ("insurance", "healthcare", "gtm")

console = Console()

_DECISION_STYLE = {
    "allow": ("green", "✓"),
    "deny": ("red", "✗"),
    "review": ("yellow", "⚑"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AIControl Demo Runner")
    parser.add_argument("--scenario", required=True, choices=sorted(SCENARIO_NAMES),
                        help=f"Scenario to run: {', '.join(sorted(SCENARIO_NAMES))}")
    parser.add_argument("--mode", choices=["fast", "walkthrough"], default="walkthrough",
                        help="fast = no pauses, walkthrough = press ENTER between rows")
    parser.add_argument("--live", action="store_true",
                        help="Use the real OpenAI API instead of the fixture transcript")
    return parser


def render(harness: DemoHarness, results: list[dict], mode: str) -> None:
    spec = harness.spec
    console.print()
    console.print(Panel(
        f"[bold white]{spec['name']}[/bold white]\n[white]{spec['description']}[/white]",
        style="blue", box=box.ROUNDED,
    ))
    console.print()

    table = Table(title="Session Summary", box=box.SIMPLE_HEAVY)
    table.add_column("Tool", style="cyan")
    table.add_column("Decision", width=10)
    table.add_column("Policy", style="dim")
    table.add_column("Workflow", style="dim")

    for r in results:
        color, icon = _DECISION_STYLE.get(r["decision"], ("white", "?"))
        table.add_row(
            r["tool_name"],
            f"[{color}]{icon} {r['decision'].upper()}[/{color}]",
            r.get("policy_name") or "—",
            r.get("workflow") or "—",
        )
        if mode == "walkthrough":
            console.print(table)
            console.print("\n[dim]Press ENTER to continue...[/dim]", end="")
            input()
            table = Table(box=box.SIMPLE_HEAVY, show_header=False)
            table.add_column()
            table.add_column()
            table.add_column()
            table.add_column()
        else:
            time.sleep(0.3)

    console.print(table)
    if harness.skipped_beats:
        console.print()
        for beat in harness.skipped_beats:
            console.print(f"[dim]Skipped (community edition): {beat}[/dim]")
    console.print()


async def _run(scenario: str, live: bool, mode: str) -> None:
    harness = DemoHarness(scenario=scenario, live=live)
    results = await harness.run(mode=mode)
    render(harness, results, mode)


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(_run(args.scenario, args.live, args.mode))


if __name__ == "__main__":
    main()
