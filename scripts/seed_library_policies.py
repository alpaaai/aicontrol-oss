"""Seed the 18 real-world library policies into the database.

Run: PYTHONPATH=/home/deven/aicontrol python scripts/seed_library_policies.py
Idempotent — safe to run multiple times.
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.models.database import async_session_factory

LIBRARY_POLICIES = [
    # ── Dangerous Operations (Standard + Strict) ─────────────────────────────
    {
        "name": "block_shell_execution",
        "description": "Block all shell execution tools — bash, exec, system calls",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": [
                "bash", "exec_command", "run_shell",
                "execute_code", "subprocess", "system_call",
            ]
        },
        "action": "deny",
        "active": False,
        "library": True,
        "priority": 10,
        "category": "Dangerous Operations",
        "severity": "critical",
        "compliance_frameworks": ["SOC2", "ISO27001"],
    },
    {
        "name": "block_file_deletion",
        "description": "Block destructive file and database deletion operations",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": [
                "delete_file", "remove_file", "unlink",
                "rmdir", "drop_table", "truncate_table",
            ]
        },
        "action": "deny",
        "active": False,
        "library": True,
        "priority": 11,
        "category": "Dangerous Operations",
        "severity": "critical",
        "compliance_frameworks": ["SOC2"],
    },
    {
        "name": "block_cloud_metadata_access",
        "description": "Block access to cloud instance metadata service URLs (SSRF protection)",
        "rule_type": "parameter_match",
        "condition": {
            "parameter_match": {
                "url": {"contains_any": ["169.254.169.254", "fd00:ec2::254"]}
            }
        },
        "action": "deny",
        "active": False,
        "library": True,
        "priority": 12,
        "category": "Dangerous Operations",
        "severity": "critical",
        "compliance_frameworks": ["SOC2", "CIS"],
    },
    {
        "name": "block_sensitive_file_reads",
        "description": "Block reads of known sensitive system files",
        "rule_type": "parameter_match",
        "condition": {
            "parameter_match": {
                "path": {
                    "contains_any": [
                        "/etc/passwd", "/etc/shadow",
                        "/.ssh/id_rsa", "/.aws/credentials",
                    ]
                }
            }
        },
        "action": "deny",
        "active": False,
        "library": True,
        "priority": 13,
        "category": "Dangerous Operations",
        "severity": "critical",
        "compliance_frameworks": ["SOC2", "CIS"],
    },
    # ── Data Protection (Strict) ──────────────────────────────────────────────
    {
        "name": "block_wildcard_queries",
        "description": "Block wildcard (bulk) record queries — id set to wildcard",
        "rule_type": "parameter_match",
        "condition": {
            "parameter_match": {
                "id": {"equals": "*"},
            }
        },
        "action": "deny",
        "active": False,
        "library": True,
        "priority": 20,
        "category": "Data Protection",
        "severity": "high",
        "compliance_frameworks": ["SOC2", "GDPR"],
    },
    {
        "name": "block_large_record_exports",
        "description": "Block tool calls requesting more than 1,000 records",
        "rule_type": "numeric_conditions",
        "condition": {
            "numeric_conditions": {
                "limit": {"op": ">", "value": 1000}
            }
        },
        "action": "deny",
        "active": False,
        "library": True,
        "priority": 21,
        "category": "Data Protection",
        "severity": "high",
        "compliance_frameworks": ["SOC2", "GDPR"],
    },
    {
        "name": "block_prompt_injection_in_params",
        "description": "Flag tool calls with prompt injection patterns in any parameter (OWASP LLM01)",
        "rule_type": "parameter_match",
        "condition": {
            "parameter_match": {
                "*": {
                    "contains_any": [
                        "ignore previous instructions",
                        "disregard previous",
                        "bypass",
                        "jailbreak",
                        "dan mode",
                    ]
                }
            }
        },
        "action": "review",
        "active": False,
        "library": True,
        "priority": 22,
        "category": "Data Protection",
        "severity": "high",
        "compliance_frameworks": ["OWASP-LLM"],
    },
    {
        "name": "block_credential_patterns",
        "description": "Flag tool calls containing credential or API key patterns in any parameter",
        "rule_type": "parameter_match",
        "condition": {
            "parameter_match": {
                "*": {
                    "contains_any": [
                        "sk-", "sk-ant-", "api_key=",
                        "-----BEGIN RSA", "-----BEGIN PRIVATE",
                        "ghp_", "aws_secret_access",
                    ]
                }
            }
        },
        "action": "review",
        "active": False,
        "library": True,
        "priority": 23,
        "category": "Data Protection",
        "severity": "high",
        "compliance_frameworks": ["SOC2", "CIS"],
    },
    # ── Human Review Gates (opt-in) ───────────────────────────────────────────
    {
        "name": "review_write_operations",
        "description": "Send all write/create/update tool calls to human review",
        "rule_type": "tool_pattern",
        "condition": {
            "tool_name_contains": ["write", "update", "create", "insert", "patch", "modify"]
        },
        "action": "review",
        "active": False,
        "library": True,
        "priority": 30,
        "category": "Human Review Gates",
        "severity": "medium",
        "compliance_frameworks": [],
    },
    {
        "name": "review_outbound_messaging",
        "description": "Send all outbound communication tool calls to human review",
        "rule_type": "tool_pattern",
        "condition": {
            "tool_name_contains": ["send_email", "post_message", "send_sms", "notify", "alert"]
        },
        "action": "review",
        "active": False,
        "library": True,
        "priority": 31,
        "category": "Human Review Gates",
        "severity": "medium",
        "compliance_frameworks": [],
    },
    {
        "name": "review_high_value_transactions",
        "description": "Send transactions over $10,000 to human review",
        "rule_type": "numeric_conditions",
        "condition": {
            "numeric_conditions": {
                "amount": {"op": ">", "value": 10000}
            }
        },
        "action": "review",
        "active": False,
        "library": True,
        "priority": 32,
        "category": "Human Review Gates",
        "severity": "medium",
        "compliance_frameworks": [],
    },
    {
        "name": "rate_limit_external_api_calls",
        "description": "Deny external HTTP/webhook calls after 20 per hour",
        "rule_type": "rate_limit",
        "condition": {
            "rate_limit": {"max_calls": 20, "window": "60m", "on_exceed": "deny"},
            "tools": ["http_request", "post_webhook"],
        },
        "action": "deny",
        "active": False,
        "library": True,
        "priority": 33,
        "category": "Human Review Gates",
        "severity": "medium",
        "compliance_frameworks": ["SOC2"],
    },
    # ── Industry: Finance (opt-in) ────────────────────────────────────────────
    {
        "name": "block_bulk_account_lookup",
        "description": "Block wildcard account or customer ID queries — finance compliance",
        "rule_type": "parameter_match",
        "condition": {
            "parameter_match": {
                "account_id": {"equals": "*"},
                "customer_id": {"equals": "*"},
            }
        },
        "action": "deny",
        "active": False,
        "library": True,
        "priority": 40,
        "category": "Industry: Finance",
        "severity": "high",
        "compliance_frameworks": ["GLBA", "SOC2"],
    },
    {
        "name": "review_wire_transfers",
        "description": "Send wire transfer and payment initiation tool calls to human review",
        "rule_type": "tool_pattern",
        "condition": {
            "tool_name_contains": ["wire_transfer", "initiate_ach", "send_payment"]
        },
        "action": "review",
        "active": False,
        "library": True,
        "priority": 41,
        "category": "Industry: Finance",
        "severity": "high",
        "compliance_frameworks": ["GLBA", "SOC2"],
    },
    # ── Industry: Healthcare (opt-in) ─────────────────────────────────────────
    {
        "name": "deny_cross_patient_phi_access",
        "description": "Block wildcard patient ID — PHI cross-patient data protection",
        "rule_type": "parameter_match",
        "condition": {
            "parameter_match": {
                "patient_id": {"equals": "*"}
            }
        },
        "action": "deny",
        "active": False,
        "library": True,
        "priority": 50,
        "category": "Industry: Healthcare",
        "severity": "critical",
        "compliance_frameworks": ["HIPAA", "SOC2"],
    },
    {
        "name": "review_clinical_writes",
        "description": "Send clinical write operations to human review — prescription and medication safety",
        "rule_type": "tool_pattern",
        "condition": {
            "tool_name_contains": ["create_prescription", "update_medication", "write_note"]
        },
        "action": "review",
        "active": False,
        "library": True,
        "priority": 51,
        "category": "Industry: Healthcare",
        "severity": "high",
        "compliance_frameworks": ["HIPAA"],
    },
    # ── Industry: Enterprise IT (opt-in) ──────────────────────────────────────
    {
        "name": "block_iam_modifications",
        "description": "Block IAM permission changes and MFA revocation",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["grant_admin", "revoke_mfa", "add_permission", "disable_user"]
        },
        "action": "deny",
        "active": False,
        "library": True,
        "priority": 60,
        "category": "Industry: Enterprise IT",
        "severity": "critical",
        "compliance_frameworks": ["SOC2", "ISO27001"],
    },
    {
        "name": "review_infrastructure_changes",
        "description": "Send infrastructure modification tool calls to human review",
        "rule_type": "tool_pattern",
        "condition": {
            "tool_name_contains": [
                "modify_firewall", "update_dns", "deploy_config", "scale_service"
            ]
        },
        "action": "review",
        "active": False,
        "library": True,
        "priority": 61,
        "category": "Industry: Enterprise IT",
        "severity": "high",
        "compliance_frameworks": ["SOC2", "ISO27001"],
    },
]


async def seed() -> None:
    async with async_session_factory() as session:
        for p in LIBRARY_POLICIES:
            await session.execute(
                text("""
                    INSERT INTO policies
                        (id, name, description, rule_type, condition, action,
                         compliance_frameworks, severity, active,
                         library, priority, category)
                    VALUES
                        (gen_random_uuid(), :name, :description, :rule_type,
                         CAST(:condition AS jsonb), :action,
                         CAST(:compliance_frameworks AS jsonb), :severity, :active,
                         :library, :priority, :category)
                    ON CONFLICT (name) DO UPDATE SET
                        description = EXCLUDED.description,
                        rule_type = EXCLUDED.rule_type,
                        condition = EXCLUDED.condition,
                        action = EXCLUDED.action,
                        compliance_frameworks = EXCLUDED.compliance_frameworks,
                        severity = EXCLUDED.severity,
                        library = EXCLUDED.library,
                        priority = EXCLUDED.priority,
                        category = EXCLUDED.category
                """),
                {
                    "name": p["name"],
                    "description": p.get("description", ""),
                    "rule_type": p["rule_type"],
                    "condition": json.dumps(p["condition"]),
                    "action": p["action"],
                    "compliance_frameworks": json.dumps(
                        p.get("compliance_frameworks", [])
                    ),
                    "severity": p.get("severity", "medium"),
                    "active": p.get("active", False),
                    "library": p.get("library", True),
                    "priority": p.get("priority", 100),
                    "category": p.get("category"),
                },
            )
        await session.commit()
    print(f"Seeded {len(LIBRARY_POLICIES)} library policies.")


if __name__ == "__main__":
    asyncio.run(seed())
