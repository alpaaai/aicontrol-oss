import { apiClient } from "./client";

export interface LoginResponse {
  token: string;
  user: { id: string; email: string; full_name: string; role: string };
  first_login: boolean;
}

export const login = (email: string, password: string) =>
  apiClient.post<LoginResponse>("/auth/login", { email, password });
