import { apiClient } from "./client";

export interface ValidateResponse {
  valid: boolean;
  email: string;
  full_name: string;
}

export interface SetPasswordResponse {
  token: string;
  user: { id: string; email: string; full_name: string; role: string };
}

export const validateMagicLink = (token: string) =>
  apiClient.post<ValidateResponse>("/auth/magic-link/validate", { token });

export const setPassword = (token: string, password: string) =>
  apiClient.post<SetPasswordResponse>("/auth/set-password", { token, password });
