import { apiClient } from "./client";

export interface Agent {
  id: string;
  name: string;
  owner: string;
  status: "active" | "suspended";
  framework: string | null;
  model_version: string | null;
  approved_tools: string[];
  approved_by: string | null;
}

export const listAgents = () =>
  apiClient.get<Agent[]>("/agents").then((r) => r.data);

export const getAgent = (id: string) =>
  apiClient.get<Agent>(`/agents/${id}`).then((r) => r.data);

export const patchApprovedTools = (id: string, tools: string[]) =>
  apiClient
    .patch(`/agents/${id}/approved-tools`, { approved_tools: tools })
    .then((r) => r.data);

export function computeToolCoverage(
  tools: string[],
  policies: { name: string; condition: Record<string, unknown> }[]
): Array<{ tool: string; governed: boolean; policy_name: string | null }> {
  return tools.map((tool) => {
    const match = policies.find((p) =>
      JSON.stringify(p.condition).includes(tool)
    );
    return { tool, governed: !!match, policy_name: match?.name ?? null };
  });
}
