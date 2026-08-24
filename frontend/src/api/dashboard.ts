import { apiClient } from "./client";

export interface TopTool {
  tool: string;
  count: number;
}

export interface DecisionHour {
  hour: string;
  decision: string | null;
  count: number;
}

export interface DashboardSummary {
  intercepts_today: number;
  intercepts_7d: number;
  intercepts_30d: number;
  allow_count_today: number;
  deny_count_today: number;
  review_count_today: number;
  deny_rate_today: number;
  active_sessions: number;
  pending_reviews: number;
  active_agents: number;
  active_policies: number;
  top_tools: TopTool[];
  decisions_by_hour: DecisionHour[];
  active_warnings: number;
  overdue_reviews: number;
  top_denied_tool: { tool: string; count: number } | null;
  high_risk_sessions: number;
}

export const getSummary = () =>
  apiClient.get<DashboardSummary>("/dashboard/summary").then((r) => r.data);

export interface WorkflowOutcome {
  kind: string;
  count: number;
}

export interface WorkflowOutcomes {
  workflow: string;
  agents: number;
  calls: number;
  held_for_approval: number;
  denied: number;
  outcomes: WorkflowOutcome[];
}

export interface DashboardOutcomes {
  window: string;
  workflows: WorkflowOutcomes[];
}

export const getOutcomes = (window: string = "7d") =>
  apiClient.get<DashboardOutcomes>(`/dashboard/outcomes?window=${window}`).then((r) => r.data);
