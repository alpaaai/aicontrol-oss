"""Insert demo agents and sessions for manual testing and demo scenarios."""
import asyncio
import json
from sqlalchemy import text
from app.models.database import async_session_factory
from app.services.policy_loader import DEMO_SEEDS_DIR, load_yaml, push_rego_to_opa, upsert_policies

# approved_tools: lending + healthcare agents are allowlisted (P1-1 enforcement).
# All other agents use [] (unrestricted) — intentional contrast for future demo scenarios.
AGENTS = [
    {
        "id": "00000000-0000-0000-0000-000000000001",
        "name": "claims-processing-agent",
        "owner": "ai-team@acme-insurance.com",
        "status": "active",
        "tools": '[]',
    },
    {
        "id": "00000000-0000-0000-0000-000000000010",
        "name": "loan-underwriting-agent",
        "owner": "lending-team@bank.com",
        "status": "active",
        "tools": '["query_credit_bureau", "run_risk_model"]',
    },
    {
        "id": "00000000-0000-0000-0000-000000000020",
        "name": "clinical-documentation-agent",
        "owner": "clinical-ops@hospital.org",
        "status": "active",
        "tools": '["read_patient_record", "query_lab_results"]',
    },
    {
        "id": "00000000-0000-0000-0000-000000000030",
        "name": "incident-response-agent",
        "owner": "platform-ops@company.com",
        "status": "active",
        "tools": '[]',
    },
    {
        "id": "00000000-0000-0000-0000-000000000040",
        "name": "supplier-sourcing-agent",
        "owner": "procurement@manufacturer.com",
        "status": "active",
        "tools": '[]',
    },
    {
        "id": "00000000-0000-0000-0000-000000000050",
        "name": "support-resolution-agent",
        "owner": "cx-platform@company.com",
        "status": "active",
        "tools": '[]',
    },
    {
        "id": "00000000-0000-0000-0000-000000000060",
        "name": "crm-automation-agent",
        "owner": "revops@company.com",
        "status": "active",
        "tools": '[]',
    },
    {
        "id": "00000000-0000-0000-0000-000000000070",
        "name": "insurance-claims-agent",
        "owner": "claims-ops@aon.com",
        "status": "active",
        "tools": '[]',
    },
]


AGENT_APPROVED_TOOLS = {
    "00000000-0000-0000-0000-000000000010": [  # loan-underwriting-agent
        "query_credit_bureau",
        "run_risk_model",
        "get_income_verification",
        "get_employment_history",
        "approve_loan",
        "deny_loan",
    ],
    "00000000-0000-0000-0000-000000000020": [  # clinical-documentation-agent
        "read_patient_record",
        "write_soap_note",
        "get_lab_results",
        "get_medication_list",
        "schedule_followup",
    ],
    "00000000-0000-0000-0000-000000000030": [  # incident-response-agent
        "get_incident_details",
        "update_incident_status",
        "assign_ticket",
        "get_runbook",
        "restart_service",
        "send_notification",
    ],
    "00000000-0000-0000-0000-000000000040": [  # supplier-sourcing-agent
        "query_inventory_system",
        "query_approved_supplier_catalog",
        "create_purchase_order",
        "get_supplier_quote",
    ],
    "00000000-0000-0000-0000-000000000050": [  # support-resolution-agent
        "read_customer_account",
        "update_ticket_status",
        "send_email",
        "create_refund",
        "escalate_ticket",
    ],
    "00000000-0000-0000-0000-000000000060": [  # crm-automation-agent
        "update_deal_stage",
        "log_sales_activity",
        "get_account_details",
        "create_task",
        "send_follow_up",
    ],
    "00000000-0000-0000-0000-000000000070": [  # insurance-claims-agent
        "get_claim_details",
        "validate_policy_coverage",
        "process_claim_payment",
        "request_additional_info",
        "flag_for_review",
    ],
}

# export_credit_report is deliberately absent from loan-underwriting-agent —
# the V2 lending demo call 5 triggers approved_tools denial on this tool.

V2_POLICIES = [
    {
        "name": "deny_credit_bureau_rate_limit",
        "description": (
            "No agent may query the credit bureau more than 2 times in a single session. "
            "Prevents bulk data extraction via repeated single-record queries."
        ),
        "rule_type": "rate_limit",
        "condition": {
            "tools": ["query_credit_bureau"],
            "rate_limit": {
                "window": "session",
                "max_calls": 2,
            },
        },
        "action": "deny",
        "severity": "high",
        "compliance_frameworks": ["GLBA", "OCC", "SOC2"],
        "active": True,
    },
    {
        "name": "deny_credit_report_batch_export",
        "description": (
            "Block batch credit report export tool. "
            "NOTE: This policy references 'query_credit_report_batch' which was renamed "
            "to 'query_credit_bureau' in agent approved_tools. Policy is stale — "
            "seeded to demonstrate drift detection."
        ),
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["query_credit_report_batch"],
        },
        "action": "deny",
        "severity": "high",
        "compliance_frameworks": ["GLBA", "SOC2"],
        "active": True,
    },
]


async def seed():
    async with async_session_factory() as session:
        for agent in AGENTS:
            await session.execute(text("""
                INSERT INTO agents (id, name, owner, status, approved_tools)
                VALUES (:id, :name, :owner, :status, CAST(:tools AS jsonb))
                ON CONFLICT (id) DO NOTHING
            """), agent)
            print(f"Seeded agent: {agent['name']}  ({agent['id']})")

        await session.commit()

        for agent_id, tools in AGENT_APPROVED_TOOLS.items():
            await session.execute(
                text(
                    "UPDATE agents SET approved_tools = CAST(:tools AS jsonb) WHERE id = :id"
                ),
                {"id": agent_id, "tools": json.dumps(tools)},
            )
            print(f"Updated approved_tools: {agent_id}")

        await session.commit()

        for policy in V2_POLICIES:
            await session.execute(text("""
                INSERT INTO policies
                    (id, name, description, rule_type, condition, action,
                     compliance_frameworks, severity, active)
                VALUES
                    (gen_random_uuid(), :name, :description, :rule_type,
                     CAST(:condition AS jsonb), :action,
                     CAST(:compliance_frameworks AS jsonb), :severity, :active)
                ON CONFLICT (name) DO NOTHING
            """), {
                "name": policy["name"],
                "description": policy["description"],
                "rule_type": policy["rule_type"],
                "condition": json.dumps(policy["condition"]),
                "action": policy["action"],
                "compliance_frameworks": json.dumps(policy["compliance_frameworks"]),
                "severity": policy["severity"],
                "active": policy["active"],
            })
            print(f"Seeded policy: {policy['name']}")

        await session.commit()

        demo_policy_count = 0
        for seed_file in sorted(DEMO_SEEDS_DIR.glob("*.yaml")):
            demo_policies = load_yaml(seed_file)
            await upsert_policies(session, demo_policies)
            demo_policy_count += len(demo_policies)
            print(f"Seeded {len(demo_policies)} demo policies from {seed_file.name}")

        await push_rego_to_opa()

        print(
            f"\nDone — {len(AGENTS)} agents, {len(V2_POLICIES)} V2 policies, "
            f"{demo_policy_count} demo-scenario policies seeded."
        )


if __name__ == "__main__":
    asyncio.run(seed())
