import { useState } from 'react'
import { resolveWarning } from '../../api/warnings'
import type { PolicyWarning } from '../../api/warnings'
import { AlertTriangle, Ban, CheckCircle } from 'lucide-react'

interface Props {
  warning: PolicyWarning
  onResolved: () => void
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

const TYPE_META = {
  UNGOVERNED_TOOL: {
    label: 'Ungoverned tool',
    icon: AlertTriangle,
    className: 'bg-ac-surface-sunk text-ac-warning border border-ac-warning',
  },
  ORPHANED_POLICY: {
    label: 'Orphaned policy',
    icon: Ban,
    className: 'bg-ac-surface-sunk text-ac-muted border border-ac-hairline',
  },
} as const

export function DriftWarningRow({ warning, onResolved }: Props) {
  const [resolving, setResolving] = useState(false)
  const meta = TYPE_META[warning.warning_type as keyof typeof TYPE_META] ?? TYPE_META.ORPHANED_POLICY
  const Icon = meta.icon

  const handleResolve = async () => {
    setResolving(true)
    try {
      await resolveWarning(warning.id)
      onResolved()
    } finally {
      setResolving(false)
    }
  }

  return (
    <div className="p-4 border-b border-gray-50">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className={`flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${meta.className}`}>
              <Icon size={10} />
              {meta.label}
            </span>
            <span className="font-mono text-[12px] text-gray-600">{warning.tool_name}</span>
          </div>
          <p className="text-[12px] text-gray-600">{warning.message}</p>
          <div className="flex items-center gap-3 mt-1.5 text-[11px] text-gray-400">
            {warning.agent_name && <span>Agent: {warning.agent_name}</span>}
            {warning.policy_name && <span>Policy: {warning.policy_name}</span>}
            <span>{timeAgo(warning.created_at)}</span>
          </div>
        </div>

        {warning.is_active && (
          <button
            onClick={handleResolve}
            disabled={resolving}
            className="flex items-center gap-1 text-[12px] bg-ac-decision-allow text-white rounded-md px-3 py-1.5 font-medium
                       hover:opacity-90 disabled:opacity-50 transition-opacity shrink-0">
            <CheckCircle size={12} />
            {resolving ? 'Resolving…' : 'Resolve'}
          </button>
        )}
      </div>
    </div>
  )
}
