import { useState, useEffect, useCallback } from 'react'
import { listReviews } from '../../api/reviews'
import type { Review } from '../../api/reviews'
import { ReviewRow } from './ReviewRow'
import { EnterpriseLock } from '../../components/shared/EnterpriseLock'
import { usePoll } from '../../hooks/usePoll'
import { useLicense } from '../../hooks/useLicense'

function ReviewQueueContent() {
  const fetcher = useCallback(() => listReviews('pending'), [])
  const { data, refetch } = usePoll(fetcher, 15000)

  // listReviews returns Review[] directly
  const reviews = data ?? []

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <h3 className="text-[14px] font-medium text-gray-700">Pending Reviews</h3>
        {reviews.length > 0 && (
          <span className="bg-ac-deny-bg text-ac-deny text-[11px] font-medium px-2 py-0.5 rounded-full">
            {reviews.length}
          </span>
        )}
      </div>

      <div className="bg-ac-card border border-ac-border rounded-lg shadow-ac-card overflow-hidden">
        {reviews.length === 0 ? (
          <div className="text-center text-sm text-gray-400 py-10">
            No pending reviews. Queue is clear.
          </div>
        ) : (
          reviews.map(r => (
            <ReviewRow key={r.id} review={r} onActioned={refetch} />
          ))
        )}
      </div>

      <ResolvedReviews />
    </div>
  )
}

function ResolvedReviews() {
  const [data, setData] = useState<Review[]>([])
  const [show, setShow] = useState(false)

  useEffect(() => {
    if (show) {
      listReviews(undefined, 20).then(reviews =>
        setData(reviews.filter(x => x.status !== 'pending'))
      )
    }
  }, [show])

  return (
    <div className="mt-4">
      <button onClick={() => setShow(!show)} className="text-sm text-gray-400 hover:text-gray-600">
        {show ? 'Hide resolved' : 'Show resolved reviews'}
      </button>
      {show && (
        <div className="mt-2 bg-ac-card border border-ac-border rounded-lg shadow-ac-card overflow-hidden">
          {data.map(r => (
            <div key={r.id} className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-50 text-[13px]">
              <span className={`text-[12px] font-medium ${r.status === 'approved' ? 'text-ac-allow' : 'text-ac-deny'}`}>
                {r.status}
              </span>
              <span className="font-mono text-[12px] text-gray-600">
                {r.session_id ? r.session_id.slice(0, 8) + '…' : '—'}
              </span>
              <span className="text-gray-400 text-[11px] ml-auto">
                {r.reviewed_at ? new Date(r.reviewed_at).toLocaleString() : '—'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function ReviewQueuePage() {
  const { isEnterprise } = useLicense()
  if (!isEnterprise) {
    return (
      <div className="p-6">
        <h2 className="text-[18px] font-semibold text-ac-text-primary mb-4">Review queue</h2>
        <EnterpriseLock
          title="Review Queue — Enterprise Feature"
          description="In-dashboard review approvals require an Enterprise license. Reviews are available via Slack integration on all plans."
        >
          <div className="p-4 space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex items-center gap-3 py-2 border-b border-gray-50 text-[13px]">
                <span className="font-mono text-gray-600">session: a3f9b2c1…</span>
                <span className="text-gray-400 text-[11px] ml-auto">2h ago · pending</span>
              </div>
            ))}
          </div>
        </EnterpriseLock>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-5">
        <h2 className="text-[18px] font-semibold text-ac-text-primary">Review queue</h2>
        <p className="text-sm text-gray-400 mt-0.5">Pending HITL decisions · updates every 15s</p>
      </div>
      <ReviewQueueContent />
    </div>
  )
}
