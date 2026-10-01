import { apiClient } from "./client";

export type McpServerStatus = "pending_review" | "active" | "blocked";

export interface McpServer {
  id: string;
  name: string;
  base_url: string;
  status: McpServerStatus;
  approved_tools: string[];
  created_at: string | null;
}

export interface McpServerCreate {
  name: string;
  base_url: string;
  approved_tools?: string[];
}

export const listMcpServers = () =>
  apiClient.get<McpServer[]>("/mcp-servers").then((r) => r.data);

export const createMcpServer = (body: McpServerCreate) =>
  apiClient.post<McpServer>("/mcp-servers", body).then((r) => r.data);

export const updateMcpServerStatus = (id: string, status: McpServerStatus) =>
  apiClient.patch<McpServer>(`/mcp-servers/${id}`, { status }).then((r) => r.data);
