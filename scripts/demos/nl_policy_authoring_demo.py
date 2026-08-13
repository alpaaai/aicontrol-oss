"""Demo: LLM-assisted, deterministic-frozen policy authoring (Task 1 of
plans/v2/2026-08-12-consolidated-wedge-sprint-full-build-plan.md).

Runs entirely in-process (no live API/DB/OPA required) via
NLPolicyService.draft(), the same service POST /policies/nl-draft calls.
Shows the draft is never persisted -- it is returned for a human to review
and, only if accepted, explicitly submit via the existing POST /policies
with source="nl_draft" in the body.

Requires LLM_MOCK_ENABLED=true (no live LLM key needed). Under mock mode,
only the exact fixture string below produces a real draft -- any other
description returns rule_type=None, requires_manual_authoring=True. This
is a known scope limit of the fixture-based mock (see
plans/v2/2026-08-13-wedge-sprint-self-critique-fixes.md's open items), not
a bug in this demo; the second case below demonstrates it deliberately.

Run: LLM_MOCK_ENABLED=true PYTHONPATH=/home/deven/aicontrol python scripts/demos/nl_policy_authoring_demo.py
"""
import asyncio

from rich.console import Console
from rich.panel import Panel

from enterprise.app.services.policy_authoring.nl_policy_service import NLPolicyService

console = Console()


async def _run_case(title: str, description: str) -> None:
    service = NLPolicyService()
    draft = await service.draft(description)
    body = (
        f"description: {description!r}\n\n"
        f"rule_type: {draft.rule_type}\n"
        f"rego_condition: {draft.rego_condition}\n"
        f"confidence_notes: {draft.confidence_notes}\n"
        f"requires_admin_approval: {draft.requires_admin_approval}\n"
        f"requires_manual_authoring: {draft.requires_manual_authoring}"
    )
    console.print(Panel(body, title=title))


async def main() -> None:
    console.print("[bold]NL policy authoring demo (Task 1)[/bold]\n")

    await _run_case(
        "1. Draft produced — pending, never active",
        "Block any agent from calling delete_customer_record",
    )

    await _run_case(
        "2. Unmapped input under LLM_MOCK_ENABLED=true — falls back to manual authoring",
        "Block anything that feels like it's trying to exfiltrate data",
    )

    console.print(
        "\n[dim]Neither draft above is written to the policies table -- "
        "POST /policies/nl-draft only returns the draft. An admin must "
        "explicitly submit it via the existing POST /policies with "
        "source=\"nl_draft\" before it becomes an active, OPA-evaluated "
        "policy. The endpoint itself requires an enterprise license "
        "(app.core.license_gate.require_enterprise_license).[/dim]"
    )


if __name__ == "__main__":
    asyncio.run(main())
