"""Insert demo agents and sessions for manual testing and demo scenarios."""
import asyncio
from sqlalchemy import text
from app.models.database import async_session_factory

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
        print(f"\nDone — {len(AGENTS)} agents seeded.")


if __name__ == "__main__":
    asyncio.run(seed())
