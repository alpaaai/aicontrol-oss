import { apiClient } from "./client";

export interface ActivityLogEntry {
  id: string;
  user_email: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface ActivityLogResponse {
  logs: ActivityLogEntry[];
  total: number;
}

export interface ActivityLogFilters {
  action?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export const listActivityLog = (filters: ActivityLogFilters = {}) =>
  apiClient
    .get<ActivityLogResponse>("/dashboard/activity-log", { params: filters })
    .then((r) => r.data);
