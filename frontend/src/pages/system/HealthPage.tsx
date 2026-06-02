import { useCallback } from 'react'
import { usePoll } from '../../hooks/usePoll'
import { getHealth } from '../../api/health'
import { EnterpriseLock } from '../../components/shared/EnterpriseLock'
import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { useLicense } from '../../hooks/useLicense'

type StatusLevel = 'healthy' | 'degraded' | 'unreachable' | 'unknown'

function StatusBadge({ status }: { status: string }) {
  const normalized = status as StatusLevel
  const config: Record<StatusLevel, { icon: React.ReactNode; color: string; label: string }> = {
    healthy:     { icon: <CheckCircle size={13} />, color: 'text-green-600',  label: 'Healthy' },
    degraded:    { icon: <AlertTriangle size={13} />, color: 'text-amber-500', label: 'Degraded' },
    unreachable: { icon: <XCircle size={13} />, color: 'text-red-500',      label: 'Unreachable' },
    unknown:     { icon: <AlertTriangle size={13} />, color: 'text-gray-400', label: 'Unknown' },
  }
  const c = config[normalized] ?? config.unknown
  return (
    <span className={`flex items-center gap-1.5 font-medium text-[13px] ${c.color}`}>
      {c.icon} {c.label}
    </span>
  )
}

function HealthContent() {
  const fetcher = useCallback(() => getHealth(), [])
  const { data, loading } = usePoll(fetcher, 30000)

  if (loading && !data) return <div className="h-24 bg-gray-50 rounded animate-pulse" />

  return (
    <div className="space-y-3">
      {[
        { label: 'API Service',       value: data?.status === 'ok' ? 'healthy' : 'degraded' },
        { label: 'OPA Policy Engine', value: data?.opa_status ?? 'unknown' },
        { label: 'Drift Detector',    value: data?.drift_detector_status ?? 'unknown' },
      ].map(item => (
        <div key={item.label}
          className="flex items-center justify-between bg-white border border-gray-200 rounded-[10px] px-4 py-3">
          <span className="text-[13px] text-gray-700">{item.label}</span>
          {item.value === 'enterprise_only'
            ? <span className="text-[12px] text-purple-600">Enterprise only</span>
            : <StatusBadge status={item.value} />
          }
        </div>
      ))}

      <p className="text-[11px] text-gray-400">Refreshes every 30 seconds</p>
    </div>
  )
}

export function HealthPage() {
  const { isEnterprise } = useLicense()
  if (!isEnterprise) {
    return (
      <div className="p-6">
        <h2 className="text-[18px] font-semibold text-ac-text-primary mb-4">System health</h2>
        <EnterpriseLock
          title="OPA Health Monitor — Enterprise"
          description="Detailed OPA status, fail-closed state, and drift detector health require an Enterprise license."
        >
          <div className="p-4 space-y-2">
            {['API Service — Healthy', 'OPA Policy Engine — ●●●', 'Drift Detector — ●●●'].map(item => (
              <div key={item} className="text-sm text-gray-500 py-1 border-b border-gray-100">{item}</div>
            ))}
          </div>
        </EnterpriseLock>
      </div>
    )
  }

  return (
    <div className="p-6">
      <h2 className="text-[18px] font-semibold text-ac-text-primary mb-5">System health</h2>
      <HealthContent />
    </div>
  )
}
