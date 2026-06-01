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

export interface ActivityLogFilters {
  limit?: number
  offset?: number
  action?: string
  date_from?: string
  date_to?: string
}

export const listActivityLog = (filters: ActivityLogFilters = {}) =>
  apiClient.get<ActivityLogResponse>('/dashboard/activity-log', {
    params: { limit: 50, offset: 0, ...filters },
  }).then(r => r.data)
