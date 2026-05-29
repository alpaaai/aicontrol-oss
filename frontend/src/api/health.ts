import { apiClient } from './client'

export interface HealthResponse {
  status: string
  service: string
  opa_status?: 'healthy' | 'degraded' | 'unreachable' | 'unknown' | 'enterprise_only'
  drift_detector_status?: 'healthy' | 'degraded' | 'unknown' | 'enterprise_only'
}

export const getHealth = () =>
  apiClient.get<HealthResponse>('/health').then(r => r.data)
