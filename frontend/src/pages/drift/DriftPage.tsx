import { useState, useEffect, useCallback } from 'react'
import { listWarnings } from '../../api/warnings'
import type { PolicyWarning } from '../../api/warnings'
import { DriftWarningRow } from './DriftWarningRow'
import { EnterpriseLock } from '../../components/shared/EnterpriseLock'
import { usePoll } from '../../hooks/usePoll'
import { useLicense } from '../../hooks/useLicense'

function DriftPageContent() {
  const fetcher = useCallback(() => listWarnings(true), [])
  const { data, refetch } = usePoll(fetcher, 15000)

  const warnings = data ?? []

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <h3 className="text-[14px] font-medium text-gray-700">Active warnings</h3>
        {warnings.length > 0 && (
          <span className="bg-ac-decision-deny-soft text-ac-decision-deny text-[11px] font-medium px-2 py-0.5 rounded-full">
            {warnings.length}
          </span>
        )}
      </div>

      <div className="bg-ac-surface-card border border-ac-hairline rounded-lg shadow-ac-surface-card overflow-hidden">
        {warnings.length === 0 ? (
          <div className="text-center text-sm text-gray-400 py-10">
            No active drift warnings. Policy coverage is in sync.
          </div>
        ) : (
          warnings.map(w => (
            <DriftWarningRow key={w.id} warning={w} onResolved={refetch} />
          ))
        )}
      </div>

      <ResolvedWarnings />
    </div>
  )
}

function ResolvedWarnings() {
  const [data, setData] = useState<PolicyWarning[]>([])
  const [show, setShow] = useState(false)

  useEffect(() => {
    if (show) {
      listWarnings(false).then(warnings =>
        setData(warnings.filter(w => !w.is_active))
      )
    }
  }, [show])

  return (
    <div className="mt-4">
      <button onClick={() => setShow(!show)} className="text-sm text-gray-400 hover:text-gray-600">
        {show ? 'Hide resolved' : 'Show resolved warnings'}
      </button>
      {show && (
        <div className="mt-2 bg-ac-surface-card border border-ac-hairline rounded-lg shadow-ac-surface-card overflow-hidden">
          {data.length === 0 ? (
            <div className="text-center text-sm text-gray-400 py-6">No resolved warnings yet.</div>
          ) : (
            data.map(w => (
              <div key={w.id} className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-50 text-[13px]">
                <span className="font-mono text-[12px] text-gray-600">{w.tool_name}</span>
                <span className="text-gray-500 text-[12px] truncate">{w.message}</span>
                <span className="text-gray-400 text-[11px] ml-auto">
                  {w.resolved_at ? new Date(w.resolved_at).toLocaleString() : '—'}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export function DriftPage() {
  const { isEnterprise } = useLicense()
  if (!isEnterprise) {
    return (
      <div className="p-6">
        <h2 className="text-[18px] font-semibold text-ac-ink mb-4">Policy drift</h2>
        <EnterpriseLock
          title="Policy Drift — Enterprise Feature"
          description="Automated drift detection and the warning feed require an Enterprise license."
        >
          <div className="p-4 space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex items-center gap-3 py-2 border-b border-gray-50 text-[13px]">
                <span className="font-mono text-gray-600">tool: send_wire_transfer</span>
                <span className="text-gray-400 text-[11px] ml-auto">2h ago · active</span>
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
        <h2 className="text-[18px] font-semibold text-ac-ink">Policy drift</h2>
        <p className="text-sm text-gray-400 mt-0.5">Ungoverned tools and orphaned policies · updates every 15s</p>
      </div>
      <DriftPageContent />
    </div>
  )
}
