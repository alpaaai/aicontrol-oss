import { apiClient } from './client'

export interface ActivityLogEntry {
  id: string
  user_email: string | null
  action: string
  resource_type: string | null
  resource_id: string | null
  before_state: Record<string, unknown> | null
  after_state: Record<string, unknown> | null
  ip_address: string | null
  created_at: string
}

export interface ActivityLogResponse {
  logs: ActivityLogEntry[]
  total: number
}

export const listActivityLog = (limit = 50, offset = 0) =>
  apiClient.get<ActivityLogResponse>('/dashboard/activity-log', { params: { limit, offset } }).then(r => r.data)
