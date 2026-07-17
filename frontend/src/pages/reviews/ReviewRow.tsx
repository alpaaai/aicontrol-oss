import { useState } from 'react'
import { actionReview } from '../../api/reviews'
import type { Review } from '../../api/reviews'
import { CheckCircle, XCircle, Clock } from 'lucide-react'

interface Props {
  review: Review
  onActioned: () => void
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function isOverdue(review: Review): boolean {
  if (review.response_deadline) {
    return Date.now() > new Date(review.response_deadline).getTime()
  }
  return Date.now() - new Date(review.created_at).getTime() > 4 * 3600000
}

export function ReviewRow({ review, onActioned }: Props) {
  const [approving, setApproving] = useState(false)
  const [denying, setDenying] = useState(false)
  const [note, setNote] = useState('')
  const [showNote, setShowNote] = useState(false)
  const overdue = isOverdue(review)

  const handleAction = async (action: 'approve' | 'deny') => {
    if (action === 'approve') setApproving(true)
    else setDenying(true)
    try {
      await actionReview(review.id, action, note || undefined)
      onActioned()
    } finally {
      setApproving(false)
      setDenying(false)
    }
  }

  return (
    <div className={`p-4 border-b border-gray-50 ${overdue ? 'bg-ac-deny-bg/30' : ''}`}>
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          {(review.tool_name || review.tool_parameters) && (
            <div className="mb-2 bg-gray-50 rounded-lg px-3 py-2">
              <p className="text-[11px] font-medium text-gray-700 mb-0.5">
                {review.tool_name ?? 'Unknown tool'}
              </p>
              {review.tool_parameters && (
                <p className="text-[11px] font-mono text-gray-500 truncate">
                  {review.tool_parameters}
                </p>
              )}
            </div>
          )}
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-[12px] font-medium text-gray-800">
              Session: {review.session_id ? review.session_id.slice(0, 8) + '…' : '—'}
            </span>
            {overdue && (
              <span className="flex items-center gap-1 text-[10px] text-ac-deny font-medium">
                <Clock size={10} /> Overdue
              </span>
            )}
          </div>
          {review.assigned_to && (
            <p className="text-[11px] text-ac-text-muted mb-1">
              Assigned to: <span className="font-medium">{review.assigned_to}</span>
            </p>
          )}
          {review.review_note && (
            <p className="text-[12px] text-gray-500 truncate">{review.review_note}</p>
          )}
          <div className="flex items-center gap-3 mt-1.5 text-[11px] text-gray-400">
            <span>{timeAgo(review.created_at)}</span>
            {review.response_deadline && (
              <span className={`${overdue ? 'text-ac-deny font-medium' : 'text-gray-400'}`}>
                Due {new Date(review.response_deadline).toLocaleString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                  hour12: false,
                })}
              </span>
            )}
            <span
              className={`font-medium ${
                review.status === 'pending' ? 'text-ac-review' :
                review.status === 'approved' ? 'text-ac-allow' : 'text-ac-deny'
              }`}
            >
              {review.status}
            </span>
          </div>

          {showNote && (
            <input
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Add a note (optional)"
              className="mt-2 w-full border border-ac-border rounded-lg px-2.5 py-1.5 text-[12px] outline-none focus:ring-2 focus:ring-ac-primary/20"
            />
          )}
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => setShowNote(!showNote)}
            className="text-[11px] text-gray-400 hover:text-gray-600 border border-ac-border rounded-md px-2 py-1">
            {showNote ? 'Hide' : 'Note'}
          </button>
          <button
            onClick={() => handleAction('approve')} disabled={approving || denying}
            className="flex items-center gap-1 text-[12px] bg-ac-allow text-white rounded-md px-3 py-1.5 font-medium
                       hover:opacity-90 disabled:opacity-50 transition-opacity">
            <CheckCircle size={12} />
            {approving ? 'Approving…' : 'Approve'}
          </button>
          <button
            onClick={() => handleAction('deny')} disabled={approving || denying}
            className="flex items-center gap-1 text-[12px] bg-ac-deny text-white rounded-md px-3 py-1.5 font-medium
                       hover:opacity-90 disabled:opacity-50 transition-opacity">
            <XCircle size={12} />
            {denying ? 'Denying…' : 'Deny'}
          </button>
        </div>
      </div>
    </div>
  )
}
