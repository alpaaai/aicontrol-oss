import { apiClient } from "./client";

export interface OrgSettings {
  org_name: string;
  timezone: string;
}

export const getOrgSettings = () =>
  apiClient.get<OrgSettings>("/org-settings");
