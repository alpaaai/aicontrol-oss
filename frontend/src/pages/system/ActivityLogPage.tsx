import { useState, useEffect, useCallback } from 'react'
import { listActivityLog } from '../../api/activityLog'
import type { ActivityLogEntry, ActivityLogFilters } from '../../api/activityLog'
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

const ACTION_OPTIONS = [
  { value: '', label: 'All actions' },
  { value: 'policy.create',  label: 'Created policy' },
  { value: 'policy.update',  label: 'Updated policy' },
  { value: 'policy.delete',  label: 'Deleted policy' },
  { value: 'agent.create',   label: 'Created agent' },
  { value: 'agent.update',   label: 'Updated agent' },
  { value: 'agent.delete',   label: 'Deleted agent' },
  { value: 'token.create',   label: 'Created token' },
  { value: 'token.revoke',   label: 'Revoked token' },
  { value: 'user.login',     label: 'Logged in' },
  { value: 'user.logout',    label: 'Logged out' },
]

function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  })
}

function StateSection({ label, state, accent }: { label: string; state: Record<string, unknown>; accent: string }) {
  const entries = Object.entries(state)
  if (entries.length === 0) return null
  return (
    <div>
      <p className={`text-[10px] font-semibold uppercase tracking-wider mb-2 ${accent}`}>{label}</p>
      <div className="space-y-1">
        {entries.map(([k, v]) => (
          <div key={k} className="flex gap-3 text-[12px]">
            <span className="text-slate-400 font-mono min-w-[140px] shrink-0">{k}</span>
            <span className="text-slate-700 font-mono break-all">
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
    <div className="border-b border-gray-100 last:border-0">
      <div
        onClick={() => hasDetail && setExpanded(e => !e)}
        className={`flex items-start gap-3 px-4 py-3 transition-colors rounded-lg
          ${hasDetail ? 'cursor-pointer hover:bg-gray-50/70' : ''}`}
      >
        <span className="mt-1 text-slate-300 shrink-0 w-[13px]">
          {hasDetail
            ? (expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />)
            : null}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-slate-800">{actionLabel(entry.action)}</p>
          <p className="text-[12px] text-slate-400 mt-0.5">
            {entry.user_email ?? 'system'} &middot; {formatDate(entry.created_at)}
          </p>
        </div>
      </div>

      {expanded && hasDetail && (
        <div className="ml-8 mr-3 mb-3">
          <div
            className="bg-white rounded-xl border border-slate-200/80 overflow-hidden"
            style={{ boxShadow: '0 2px 12px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04)' }}
          >
            {(entry.ip_address || entry.resource_type || entry.resource_id) && (
              <div className="px-4 py-3 border-b border-slate-100 flex flex-wrap gap-x-6 gap-y-2">
                {entry.ip_address && (
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-0.5">IP Address</p>
                    <p className="text-[12px] font-mono text-slate-600">{entry.ip_address}</p>
                  </div>
                )}
                {(entry.resource_type || entry.resource_id) && (
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-0.5">Resource</p>
                    <p className="text-[12px] font-mono text-slate-600">
                      {[entry.resource_type, entry.resource_id].filter(Boolean).join(' · ')}
                    </p>
                  </div>
                )}
              </div>
            )}

            {(entry.before_state || entry.after_state) && (
              <div className={`grid ${entry.before_state && entry.after_state ? 'grid-cols-2 divide-x divide-slate-100' : 'grid-cols-1'}`}>
                {entry.before_state && (
                  <div className="px-4 py-3 bg-red-50/40">
                    <StateSection label="Before" state={entry.before_state} accent="text-red-400" />
                  </div>
                )}
                {entry.after_state && (
                  <div className="px-4 py-3 bg-emerald-50/40">
                    <StateSection label="After" state={entry.after_state} accent="text-emerald-500" />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

const inputClass = "border border-ac-border rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 bg-white"

function ActivityFilters({ onFilter }: { onFilter: (f: ActivityLogFilters) => void }) {
  const [action, setAction] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const apply = () => onFilter({ action: action || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined, offset: 0 })
  const reset = () => { setAction(''); setDateFrom(''); setDateTo(''); onFilter({ offset: 0 }) }

  return (
    <div className="flex flex-wrap gap-3 items-end mb-5">
      <div>
        <label className="text-[11px] text-ac-text-muted block mb-1">Action</label>
        <select value={action} onChange={e => setAction(e.target.value)} className={inputClass}>
          {ACTION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>
      <div>
        <label className="text-[11px] text-ac-text-muted block mb-1">From</label>
        <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className={inputClass} />
      </div>
      <div>
        <label className="text-[11px] text-ac-text-muted block mb-1">To</label>
        <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className={inputClass} />
      </div>
      <button onClick={apply} className="bg-ac-primary text-white rounded-lg px-4 py-1.5 text-sm font-medium hover:bg-ac-primary/90">
        Apply
      </button>
      <button onClick={reset} className="text-sm text-ac-text-muted hover:text-ac-text-primary px-2">
        Reset
      </button>
    </div>
  )
}

export function ActivityLogPage() {
  const [data, setData] = useState<ActivityLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState<ActivityLogFilters>({})

  const load = useCallback((f: ActivityLogFilters) => {
    setLoading(true)
    listActivityLog(f)
      .then(r => { setData(r.logs); setTotal(r.total) })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load({}) }, [load])

  const handleFilter = (f: ActivityLogFilters) => {
    const next = { ...filters, ...f }
    setFilters(next)
    load(next)
  }

  return (
    <div className="p-6 max-w-3xl">
      <div className="mb-5 animate-fade-up">
        <h2 className="text-[18px] font-semibold text-ac-text-primary">Activity audit</h2>
        <p className="text-sm text-ac-text-muted mt-0.5">
          All changes made by users — who changed what and when
          {total > 0 && <span className="ml-2 text-ac-text-muted">({total} entries)</span>}
        </p>
      </div>

      <ActivityFilters onFilter={handleFilter} />

      {loading && (
        <div className="space-y-2">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-14 bg-gray-50 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {!loading && data.length === 0 && (
        <p className="text-sm text-ac-text-muted py-10 text-center">
          No activity recorded yet. Changes to policies, agents, and tokens will appear here.
        </p>
      )}

      {!loading && data.length > 0 && (
        <div className="rounded-xl border border-ac-border overflow-hidden bg-white">
          {data.map(entry => (
            <ActivityRow key={entry.id} entry={entry} />
          ))}
        </div>
      )}
    </div>
  )
}
