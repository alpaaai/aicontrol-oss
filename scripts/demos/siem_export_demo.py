"""Demo: outbound SIEM export (Task 8 of
plans/v2/2026-08-12-consolidated-wedge-sprint-full-build-plan.md).

Starts a local webhook receiver, dispatches a sample deny audit event
through the same enterprise.app.services.audit_export.dispatch code path
that app.services.audit_writer.write_event now fires (fire-and-forget)
whenever a business-or-above license is active, shows the receiver got the
POST, then kills the receiver and shows a failed delivery leaves the
checkpoint unchanged (so the event isn't silently dropped).

Runs entirely in-process (no live API/Postgres/OPA required).

Run: PYTHONPATH=/home/deven/aicontrol python scripts/demos/siem_export_demo.py
"""
import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from rich.console import Console
from rich.panel import Panel

from enterprise.app.services.audit_export.dispatch import AuditEventRecord
from enterprise.app.services.audit_export.webhook_exporter import WebhookExporter

console = Console()

received: list[dict] = []


class _ReceiverHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 (http.server's naming convention)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        received.append(json.loads(body))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):  # silence default request logging
        pass


def _sample_deny_record() -> AuditEventRecord:
    return AuditEventRecord(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        agent_name="claims-processing-agent",
        tool_name="delete_customer_record",
        tool_parameters={"customer_id": "cus_88213"},
        decision="deny",
        decision_reason="blocked by policy: block_dangerous_tools",
        policy_name="block_dangerous_tools",
        duration_ms=12,
        created_at=datetime.now(timezone.utc),
    )


async def main() -> None:
    console.print("[bold]Outbound SIEM export demo (webhook)[/bold]\n")

    server = HTTPServer(("127.0.0.1", 0), _ReceiverHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    checkpoint_path = "/tmp/siem_export_demo.checkpoint"
    exporter = WebhookExporter(webhook_url=f"http://127.0.0.1:{port}/", checkpoint_path=checkpoint_path)

    record = _sample_deny_record()
    result = await exporter.export(record)
    console.print(Panel(
        f"decision: {record.decision}\ntool_name: {record.tool_name}\n\n"
        f"delivered: [green]{result.delivered}[/green]\n"
        f"receiver saw {len(received)} POST(s): {received}",
        title="1. Receiver running — event delivered",
    ))

    server.shutdown()
    thread.join(timeout=2)

    record2 = _sample_deny_record()
    result2 = await exporter.export(record2)
    console.print(Panel(
        f"delivered: [red]{result2.delivered}[/red]\n"
        f"error: {result2.error}\n"
        f"checkpoint unchanged since last success: "
        f"{exporter.checkpoint_unchanged_since_last_success()}",
        title="2. Receiver killed — delivery fails, checkpoint does not advance",
    ))

    console.print(
        "\n[dim]This is the exact code path app.services.audit_writer.write_event "
        "now fires (fire-and-forget, gated on a business-or-above license) for every "
        "audit event once an admin configures a target via "
        "POST /audit-export-configs.[/dim]"
    )


if __name__ == "__main__":
    asyncio.run(main())
