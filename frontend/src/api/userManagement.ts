import { apiClient } from "./client";

export interface MagicLinkResult {
  user: { id: string; email: string; full_name: string; role: string };
  magic_link: string;
}

export const createUser = (
  full_name: string,
  email: string,
  role: string,
): Promise<MagicLinkResult> =>
  apiClient.post("/users", { full_name, email, role }).then((r) => r.data);

export const updateUser = (
  id: string,
  data: { is_active?: boolean; role?: string },
) => apiClient.patch(`/users/${id}`, data).then((r) => r.data);

export const deleteUser = (id: string) => apiClient.delete(`/users/${id}`);

export const regenerateInvite = (id: string): Promise<MagicLinkResult> =>
  apiClient.post(`/users/${id}/regenerate-invite`).then((r) => r.data);
