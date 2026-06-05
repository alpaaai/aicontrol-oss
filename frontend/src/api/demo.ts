import axios from "axios";
import { apiClient } from "./client";

export interface DemoStatus {
  seeded: boolean;
  demo_token: string | null;
}

export interface SeedResponse {
  ok: boolean;
  demo_token: string;
}

export interface ResetResponse {
  ok: boolean;
}

export interface InterceptResponse {
  decision: "allow" | "deny" | "review";
  reason: string;
  policy_name?: string;
  audit_event_id?: string;
  duration_ms?: number;
}

export const getDemoStatus = (): Promise<DemoStatus> =>
  apiClient.get<DemoStatus>("/demo/status").then((r) => r.data);

export const seedDemo = (): Promise<SeedResponse> =>
  apiClient.post<SeedResponse>("/demo/seed").then((r) => r.data);

export const resetDemo = (): Promise<ResetResponse> =>
  apiClient.post<ResetResponse>("/demo/reset").then((r) => r.data);

export const runIntercept = (
  demoToken: string,
  payload: {
    session_id: string;
    agent_id: string;
    agent_name: string;
    tool_name: string;
    tool_parameters: Record<string, unknown>;
    sequence_number: number;
  }
): Promise<InterceptResponse> => {
  const baseURL = import.meta.env.VITE_API_URL ?? "http://localhost:8001";
  return axios
    .post<InterceptResponse>(`${baseURL}/intercept`, payload, {
      headers: { Authorization: `Bearer ${demoToken}` },
    })
    .then((r) => r.data);
};
