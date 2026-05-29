import { useState, useEffect } from 'react'
import { listActivityLog, ActivityLogEntry } from '../../api/activityLog'

export function ActivityLogPage() {
  const [data, setData] = useState<ActivityLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listActivityLog(50, 0)
      .then(r => { setData(r.logs); setTotal(r.total) })
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="p-6">
      <div className="mb-5">
        <h2 className="text-[18px] font-semibold tracking-[-0.02em] text-gray-900">Activity Log</h2>
        <p className="text-sm text-gray-400 mt-0.5">
          All changes made by users — who changed what and when
          {total > 0 && <span className="ml-2 text-gray-300">({total} entries)</span>}
        </p>
      </div>

      <div className="bg-white border border-gray-200 rounded-[10px] overflow-hidden">
        <div className="grid grid-cols-[180px_200px_1fr_120px] gap-3 px-4 py-2.5
                        text-[11px] font-medium text-gray-400 uppercase tracking-wide
                        border-b border-gray-200 bg-gray-50">
          <div>Time</div>
          <div>User</div>
          <div>Action</div>
          <div>Resource</div>
        </div>

        {loading && (
          <div className="space-y-2 p-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-8 bg-gray-50 rounded animate-pulse" />
            ))}
          </div>
        )}

        {!loading && data.length === 0 && (
          <div className="text-center text-sm text-gray-400 py-10">
            No activity recorded yet. Changes to policies, agents, and tokens will appear here.
          </div>
        )}

        {data.map(entry => (
          <div key={entry.id}
            className="grid grid-cols-[180px_200px_1fr_120px] gap-3 px-4 py-2.5
                       text-[13px] border-b border-gray-50">
            <div className="font-mono text-[11px] text-gray-500">
              {new Date(entry.created_at).toLocaleString('en-US', {
                month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
              })}
            </div>
            <div className="text-gray-600 truncate">{entry.user_email ?? 'system'}</div>
            <div className="font-mono text-[12px] text-gray-700">{entry.action}</div>
            <div className="text-[12px] text-gray-500 truncate font-mono">
              {entry.resource_type && entry.resource_id
                ? `${entry.resource_type}:${entry.resource_id.slice(0, 8)}`
                : '—'}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
