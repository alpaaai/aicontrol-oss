import { apiClient } from "./client";

export interface CreateTokenResponse {
  token_id: string;
  role: string;
  description: string;
  agent_id: string | null;
  token: string;
}

export const createToken = (
  role: string,
  description: string,
  agent_id?: string
) =>
  apiClient
    .post<CreateTokenResponse>("/tokens", { role, description, agent_id })
    .then((r) => r.data);
