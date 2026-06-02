import { apiClient } from "./client";

export interface UserItem {
  id: string;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

export const listUsers = () =>
  apiClient.get<UserItem[]>("/users").then((r) => r.data);
