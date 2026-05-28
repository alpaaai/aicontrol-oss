import { apiClient } from "./client";

export const requestCode = (email: string) =>
  apiClient.post("/auth/request-code", { email });

export const verifyCode = (email: string, code: string) =>
  apiClient.post<{ token: string; role: string; email: string }>(
    "/auth/verify-code",
    { email, code }
  );
