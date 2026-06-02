import { apiClient } from "./client";

export interface TokenListItem {
  id: string;
  role: string;
  description: string | null;
  agent_id: string | null;
  agent_name: string | null;
  revoked: boolean;
  created_at: string | null;
}

export const listTokens = (activeOnly = false) =>
  apiClient
    .get<TokenListItem[]>("/tokens", { params: { active_only: activeOnly } })
    .then((r) => r.data);
