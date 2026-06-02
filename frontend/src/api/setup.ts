import { apiClient } from "./client";

export interface SetupStatus {
  setup_required: boolean;
}

export interface SetupCompletePayload {
  full_name: string;
  email: string;
  password: string;
  org_name: string;
  timezone: string;
}

export interface SetupCompleteResponse {
  token: string;
  user: { id: string; email: string; full_name: string; role: string };
}

export const getSetupStatus = () =>
  apiClient.get<SetupStatus>("/setup/status");

export const completeSetup = (payload: SetupCompletePayload) =>
  apiClient.post<SetupCompleteResponse>("/setup/complete", payload);
