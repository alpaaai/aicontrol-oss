import { useState } from 'react'
import { EnterpriseLock } from '../../components/shared/EnterpriseLock'
import { ReportForm } from './ReportForm'
import { ReportHistory } from './ReportHistory'
import { useLicense } from '../../hooks/useLicense'

export function ReportsPage() {
  const [refreshKey, setRefreshKey] = useState(0)
  const { isEnterprise } = useLicense()

  if (!isEnterprise) {
    return (
      <div className="p-6">
        <h2 className="text-[18px] font-semibold text-ac-text-primary mb-4">Compliance reports</h2>
        <EnterpriseLock
          title="Compliance reports — Enterprise"
          description="AI-native compliance report generation (EU AI Act, NIST AI RMF, SOC 2, ISO 42001) requires an Enterprise license."
        >
          <div className="p-4 space-y-3">
            <div className="text-sm text-gray-500">EU AI Act · SOC 2 · NIST AI RMF · ISO 42001</div>
            <div className="flex gap-2">
              {['PDF', 'Markdown', 'Both'].map(f => (
                <span key={f} className="text-xs border border-gray-200 rounded px-2 py-1 text-gray-400">{f}</span>
              ))}
            </div>
          </div>
        </EnterpriseLock>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-5">
        <h2 className="text-[18px] font-semibold text-ac-text-primary">Compliance reports</h2>
        <p className="text-sm text-gray-400 mt-0.5">AI-native compliance reporting · EU AI Act · NIST AI RMF · SOC 2 · ISO 42001</p>
      </div>
      <ReportForm onGenerated={() => setRefreshKey(k => k + 1)} />
      <ReportHistory refreshKey={refreshKey} />
    </div>
  )
}
