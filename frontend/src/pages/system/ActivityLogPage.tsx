import { useState, useEffect } from 'react'
import { listActivityLog } from '../../api/activityLog'
import type { ActivityLogEntry } from '../../api/activityLog'
import { ChevronDown, ChevronRight } from 'lucide-react'

const ACTION_LABELS: Record<string, string> = {
  'policy.create':  'Created policy',
  'policy.update':  'Updated policy',
  'policy.delete':  'Deleted policy',
  'agent.create':   'Created agent',
  'agent.update':   'Updated agent',
  'agent.delete':   'Deleted agent',
  'token.create':   'Created token',
  'token.revoke':   'Revoked token',
  'user.login':     'Logged in',
  'user.logout':    'Logged out',
}

function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  })
}

function StateSection({ label, state }: { label: string; state: Record<string, unknown> }) {
  const entries = Object.entries(state)
  if (entries.length === 0) return null
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">{label}</p>
      <div className="space-y-0.5">
        {entries.map(([k, v]) => (
          <div key={k} className="flex gap-2 text-[12px]">
            <span className="text-gray-400 font-mono min-w-[120px]">{k}</span>
            <span className="text-gray-700 font-mono break-all">
              {typeof v === 'object' ? JSON.stringify(v) : String(v ?? '—')}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ActivityRow({ entry }: { entry: ActivityLogEntry }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetail = entry.ip_address || entry.before_state || entry.after_state || entry.resource_id

  return (
    <div>
      <div
        onClick={() => hasDetail && setExpanded(e => !e)}
        className={`flex items-start gap-3 px-4 py-3 rounded-lg transition-colors
          ${hasDetail ? 'cursor-pointer hover:bg-gray-50' : ''}`}
      >
        <span className="mt-0.5 text-gray-300 shrink-0">
          {hasDetail
            ? (expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />)
            : <span className="w-[13px] inline-block" />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-gray-800">{actionLabel(entry.action)}</p>
          <p className="text-[12px] text-gray-400 mt-0.5">
            {entry.user_email ?? 'system'} &middot; {formatDate(entry.created_at)}
          </p>
        </div>
      </div>

      {expanded && hasDetail && (
        <div className="ml-10 mr-4 mb-3 px-4 py-3 bg-gray-50 rounded-lg space-y-3">
          {entry.ip_address && (
            <div>
              <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">IP address</p>
              <p className="text-[12px] font-mono text-gray-700">{entry.ip_address}</p>
            </div>
          )}
          {(entry.resource_type || entry.resource_id) && (
            <div>
              <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Resource</p>
              <p className="text-[12px] font-mono text-gray-700">
                {[entry.resource_type, entry.resource_id].filter(Boolean).join(' · ')}
              </p>
            </div>
          )}
          {entry.before_state && (
            <StateSection label="Before" state={entry.before_state} />
          )}
          {entry.after_state && (
            <StateSection label="After" state={entry.after_state} />
          )}
        </div>
      )}
    </div>
  )
}

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
    <div className="p-6 max-w-3xl">
      <div className="mb-5 animate-fade-up">
        <h2 className="text-[18px] font-semibold text-ac-text-primary">Activity audit</h2>
        <p className="text-sm text-gray-400 mt-0.5">
          All changes made by users — who changed what and when
          {total > 0 && <span className="ml-2 text-gray-300">({total} entries)</span>}
        </p>
      </div>

      {loading && (
        <div className="space-y-2">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-14 bg-gray-50 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {!loading && data.length === 0 && (
        <p className="text-sm text-gray-400 py-10 text-center">
          No activity recorded yet. Changes to policies, agents, and tokens will appear here.
        </p>
      )}

      {!loading && data.length > 0 && (
        <div>
          {data.map(entry => (
            <ActivityRow key={entry.id} entry={entry} />
          ))}
        </div>
      )}
    </div>
  )
}
