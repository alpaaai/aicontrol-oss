import { apiClient } from './client'

export type Framework = 'eu_ai_act' | 'nist_ai_rmf' | 'soc2' | 'iso_42001'
export type ReportFormat = 'pdf' | 'md' | 'both'

export interface GenerateReportBody {
  date_from: string
  date_to: string
  frameworks: Framework[]
  format: ReportFormat
}

// Matches ComplianceReportResponse from enterprise/compliance/router.py
export interface ComplianceReport {
  id: string
  tenant_id: string | null
  generated_at: string
  date_from: string
  date_to: string
  frameworks: Framework[]
  format: ReportFormat
  report_path: string
  md_path: string | null
  llm_model: string
  mock_used: boolean
  token_input: number | null
  token_output: number | null
}

// POST returns binary file — use responseType blob and trigger download at call site
export const generateReport = (body: GenerateReportBody) =>
  apiClient.post('/enterprise/compliance/report', body, { responseType: 'blob' }).then(r => r.data as Blob)

// GET returns ComplianceReport[] directly (no wrapper object)
export const listReports = () =>
  apiClient.get<ComplianceReport[]>('/enterprise/compliance/reports').then(r => r.data)

export const downloadReport = (id: string) =>
  apiClient.get(`/enterprise/compliance/reports/${id}/download`, { responseType: 'blob' }).then(r => r.data as Blob)
