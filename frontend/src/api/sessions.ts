import { apiClient } from "./client";

export interface Session {
  id: string;
  agent_id: string | null;
  risk_score: number | null;
  status: string;
  started_at: string | null;
}

export interface SessionsResponse {
  sessions: Session[];
  total: number;
}

export interface SessionEvent {
  id: string;
  session_id: string;
  tool_name: string;
  tool_parameters: string | null;
  decision: "allow" | "deny" | "review";
  decision_reason: string | null;
  policy_name: string | null;
  sequence_number: number;
  duration_ms: number | null;
  created_at: string;
}

export interface SessionDetailResponse {
  session_id: string;
  agent_id: string | null;
  risk_score: number | null;
  events: SessionEvent[];
}

export const listSessions = (limit = 50, offset = 0) =>
  apiClient
    .get<SessionsResponse>("/sessions", { params: { limit, offset } })
    .then((r) => r.data);

export const getSessionEvents = (sessionId: string) =>
  apiClient
    .get<SessionDetailResponse>(`/sessions/${sessionId}/events`)
    .then((r) => r.data);
