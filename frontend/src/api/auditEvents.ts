import { apiClient } from "./client";

export interface AuditEvent {
  id: string;
  session_id: string;
  agent_id: string;
  agent_name: string;
  tool_name: string;
  tool_parameters: string | null;
  decision: "allow" | "deny" | "review";
  decision_reason: string | null;
  policy_id: string | null;
  policy_name: string | null;
  duration_ms: number | null;
  sequence_number: number;
  created_at: string;
  tool_response: string | null;
}

export interface AuditEventsResponse {
  events: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditFilters {
  decision?: string;
  agent_id?: string;
  tool_name?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export const listAuditEvents = (filters: AuditFilters = {}) =>
  apiClient
    .get<AuditEventsResponse>("/audit-events", { params: filters })
    .then((r) => r.data);
