import { apiClient } from "./client";
import type { PolicyScope } from "./policies";

export type CoverageState = "governed" | "installed_not_firing" | "unknown";

export interface Agent {
  id: string;
  name: string;
  owner: string;
  status: "active" | "suspended";
  framework: string | null;
  model_version: string | null;
  approved_tools: string[];
  approved_by: string | null;
  system_prompt_hash: string | null;
  approved_at: string | null;
  created_at: string | null;
  last_active: string | null;
  deny_rate: number | null;
  hook: string | null;
  sdk_version: string | null;
  workflow: string | null;
  coverage_state: CoverageState;
  silent_noop_warnings: string[];
  unresolved_systems: string[];
}

export const COVERAGE_LABEL: Record<CoverageState, string> = {
  governed: "Governed",
  installed_not_firing: "Installed, no calls arriving",
  unknown: "Not connected",
};

export const listAgents = () =>
  apiClient.get<Agent[]>("/agents").then((r) => r.data);

export const getAgent = (id: string) =>
  apiClient.get<Agent>(`/agents/${id}`).then((r) => r.data);

// This endpoint already returns PolicyScope shape -- it exists to feed the
// agent's governing-policies list directly, so it skips the mapper every
// other policy consumer uses.
export const getAgentPolicies = (id: string): Promise<PolicyScope[]> =>
  apiClient.get<PolicyScope[]>(`/agents/${id}/policies`).then((r) => r.data);
