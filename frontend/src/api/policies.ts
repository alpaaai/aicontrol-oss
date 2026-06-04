import { apiClient } from "./client";

export interface Policy {
  id: string;
  name: string;
  description: string | null;
  rule_type: string;
  condition: Record<string, unknown>;
  action: string;
  severity: string | null;
  active: boolean | null;
  compliance_frameworks: string[] | null;
  applies_to_agents: number;
  created_by: string | null;
  priority: number;
  library: boolean;
  category: string | null;
}

export interface CreatePolicyBody {
  name: string;
  description?: string;
  rule_type: string;
  condition: Record<string, unknown>;
  action: string;
  severity?: string;
  compliance_frameworks?: string[];
  priority?: number;
  library?: boolean;
  category?: string;
}

export interface UpdatePolicyBody extends Partial<CreatePolicyBody> {
  active?: boolean;
}

export const listPolicies = () =>
  apiClient.get<Policy[]>("/policies").then((r) => r.data);

export const listLibraryPolicies = () =>
  apiClient.get<Policy[]>("/policies/library").then((r) => r.data);

export const getPolicy = (id: string) =>
  apiClient.get<Policy>(`/policies/${id}`).then((r) => r.data);

export const createPolicy = (body: CreatePolicyBody) =>
  apiClient.post<Policy>("/policies", body).then((r) => r.data);

export const updatePolicy = (id: string, body: UpdatePolicyBody) =>
  apiClient.put<Policy>(`/policies/${id}`, body).then((r) => r.data);

export const deletePolicy = (id: string) =>
  apiClient.delete(`/policies/${id}`).then((r) => r.data);

export interface BaselineActivateResponse {
  mode: string;
  activated: string[];
}

export const activateBaseline = (mode: "standard" | "strict") =>
  apiClient
    .post<BaselineActivateResponse>("/policies/activate-baseline", { mode })
    .then((r) => r.data);
