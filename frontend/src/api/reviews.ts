import { apiClient } from './client'

export interface Review {
  id: string
  audit_event_id: string | null
  session_id: string | null
  status: 'pending' | 'approved' | 'denied'
  reviewer: string | null
  review_note: string | null
  reviewed_at: string | null
  created_at: string
}

export const listReviews = (status?: string, limit = 50) =>
  apiClient.get<Review[]>('/reviews', { params: { status, limit } }).then(r => r.data)

export const actionReview = (id: string, action: 'approve' | 'deny', note?: string) =>
  apiClient.patch(`/reviews/${id}`, { action, note }).then(r => r.data)
