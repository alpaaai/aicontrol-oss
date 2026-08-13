"""Demo: named-human decision accountability (Task 6 of
plans/v2/2026-08-12-consolidated-wedge-sprint-full-build-plan.md).

Before this task, app/routers/reviews.py's action_review hardcoded
`review.reviewer = "dashboard"`, discarding the authenticated human's
identity. Shows the fix end to end against the real seeded DB: creates a
pending HITL review, calls the real action_review() router function
(bypassing HTTP/FastAPI dependency injection -- calling it directly with a
`human` dict shaped like require_human's real JWT payload,
{"email": ...}), confirms the review's reviewer field is the human's
email rather than "dashboard", then generates a compliance report over
that event and shows the reviewer surfaced there too, distinct from the
agent's owner.

Needs Postgres reachable (docker compose up -d). No live API server or
Slack webhook required -- action_review is called as a plain function.

Run: PYTHONPATH=/home/deven/aicontrol python scripts/demos/accountability_demo.py
"""
import asyncio
import uuid
from datetime import date, timedelta

from rich.console import Console
from rich.panel import Panel
from sqlalchemy import delete

from app.models.database import async_session_factory
from app.models.schemas import AuditEvent, HITLReview
from app.routers.reviews import ReviewActionBody, action_review
from enterprise.compliance.aggregator import aggregate_audit_events
from enterprise.compliance.md_builder import build_markdown

console = Console()

REVIEWER_EMAIL = "jane.reviewer@acme-insurance.com"


async def main() -> None:
    audit_event_id = uuid.uuid4()
    review_id = uuid.uuid4()

    async with async_session_factory() as session:
        session.add(AuditEvent(
            id=audit_event_id,
            sequence_number=1,
            agent_name="claims-processing-agent",
            tool_name="approve_claim_payment",
            tool_parameters={"claim_id": "CLM-88213", "amount_usd": 7500},
            decision="review",
            decision_reason="blocked by policy: review_high_value_claim_payment",
            policy_name="review_high_value_claim_payment",
            duration_ms=8,
        ))
        session.add(HITLReview(
            id=review_id,
            audit_event_id=audit_event_id,
            status="pending",
        ))
        await session.commit()

    try:
        console.print(Panel(
            "reviewer field before action_review(): pending (unset)\n\n"
            "Before this fix, the PATCH /reviews/{id} handler unconditionally set\n"
            "review.reviewer = \"dashboard\" here, regardless of who actually approved it.",
            title="1. Pending HITL review created",
        ))

        result = await action_review(
            review_id=review_id,
            body=ReviewActionBody(action="approve", note="Approved after manual claim review."),
            human={"email": REVIEWER_EMAIL, "type": "human"},
        )
        console.print(Panel(
            f"status: {result['status']}\nreviewer: [green]{REVIEWER_EMAIL}[/green] (not \"dashboard\")",
            title="2. action_review() called with a real human identity",
        ))

        async with async_session_factory() as session:
            ctx = await aggregate_audit_events(session, date.today() - timedelta(days=1), date.today() + timedelta(days=1))
        md = build_markdown(ctx, narratives={}, report_id=uuid.uuid4(), frameworks=["soc2"])
        idx = md.find("## Reviewed Call Detail")
        section = md[idx:idx + 500] if idx != -1 else "(section not found)"
        console.print(Panel(section, title="3. Compliance report — Reviewed Call Detail section"))

    finally:
        async with async_session_factory() as session:
            await session.execute(delete(HITLReview).where(HITLReview.id == review_id))
            await session.execute(delete(AuditEvent).where(AuditEvent.id == audit_event_id))
            await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
