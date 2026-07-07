import { apiClient } from "./client";

export interface AdmissionScanFinding {
  severity: "info" | "low" | "medium" | "high" | "critical";
  rule_id: string;
  message: string;
  location: string | null;
  raw: Record<string, unknown>;
}

export interface AdmissionScan {
  id: string;
  agent_id: string | null;
  target_type: string;
  target_ref: string;
  scanner_name: string;
  status: "pending" | "running" | "completed" | "failed";
  findings: AdmissionScanFinding[];
  severity_summary: Record<string, number>;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
}

export interface CreateAdmissionScanRequest {
  target_type: string;
  target_ref: string;
  agent_id?: string;
  scanners?: string[];
}

export const listAdmissionScans = () =>
  apiClient.get<AdmissionScan[]>("/admission-scans").then((r) => r.data);

export const getAdmissionScan = (id: string) =>
  apiClient.get<AdmissionScan>(`/admission-scans/${id}`).then((r) => r.data);

export const createAdmissionScan = (body: CreateAdmissionScanRequest) =>
  apiClient
    .post<AdmissionScan[]>("/admission-scans", body)
    .then((r) => r.data);
