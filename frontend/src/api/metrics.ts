import { apiClient } from "./client";

export interface DenyTrendPoint {
  day: string;
  decision: string;
  count: number;
}

export interface TopAgentByDeny {
  agent_name: string;
  total: number;
  deny_rate: number;
}

export interface DashboardMetrics {
  policy_hit_rate: number;
  deny_trend: DenyTrendPoint[];
  top_agents_by_deny_rate: TopAgentByDeny[];
  avg_review_seconds: number | null;
}

export const getMetrics = () =>
  apiClient.get<DashboardMetrics>("/dashboard/metrics").then((r) => r.data);
