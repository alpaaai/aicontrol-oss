import { apiClient } from "./client";

export interface OrgSettings {
  org_name: string;
  timezone: string;
  updated_at?: string;
}

export const getOrgSettings = () =>
  apiClient.get<OrgSettings>("/org-settings");

export const updateOrgSettings = (data: { org_name?: string; timezone?: string }) =>
  apiClient.put<OrgSettings>("/org-settings", data);
