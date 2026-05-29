import { apiClient } from "./client";

export interface PolicyWarning {
  id: string;
  warning_type: string;
  agent_id: string | null;
  agent_name: string | null;
  policy_id: string | null;
  policy_name: string | null;
  tool_name: string;
  message: string;
  is_active: boolean;
  created_at: string;
  resolved_at: string | null;
}

export const listWarnings = (isActive = true) =>
  apiClient
    .get<PolicyWarning[]>("/warnings", { params: { is_active: isActive } })
    .then((r) => r.data);

export const resolveWarning = (id: string) =>
  apiClient.patch(`/warnings/${id}/resolve`).then((r) => r.data);
