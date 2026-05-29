import { useState, useEffect } from 'react'
import { listReports, downloadReport, ComplianceReport } from '../../api/reports'
import { Download } from 'lucide-react'

interface Props { refreshKey: number }

export function ReportHistory({ refreshKey }: Props) {
  const [reports, setReports] = useState<ComplianceReport[]>([])
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    // listReports returns ComplianceReport[] directly
    listReports().then(r => setReports(r)).finally(() => setLoading(false))
  }, [refreshKey])

  const handleDownload = async (report: ComplianceReport) => {
    setDownloading(report.id)
    try {
      const blob = await downloadReport(report.id)
      const ext = report.format === 'both' ? 'zip' : report.format
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `aicontrol-compliance-${report.date_from}-${report.date_to}.${ext}`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="mt-5">
      <h3 className="text-[14px] font-semibold text-gray-900 mb-3">Report History</h3>
      <div className="bg-white border border-gray-200 rounded-[10px] overflow-hidden">
        {loading && <div className="h-10 bg-gray-50 animate-pulse m-4 rounded" />}
        {!loading && reports.length === 0 && (
          <div className="text-center text-sm text-gray-400 py-8">No reports generated yet.</div>
        )}
        {reports.map(r => (
          <div key={r.id}
            className="flex items-center gap-3 px-4 py-3 border-b border-gray-50 text-[13px]">
            <div className="flex-1">
              <p className="text-gray-700">
                {r.frameworks.join(', ')} · {r.date_from} to {r.date_to}
              </p>
              <p className="text-[11px] text-gray-400 mt-0.5">
                {new Date(r.generated_at).toLocaleString()} · {r.format.toUpperCase()}
                {r.mock_used && <span className="ml-2 text-amber-500">mock</span>}
              </p>
            </div>
            <button
              onClick={() => handleDownload(r)}
              disabled={downloading === r.id}
              className="flex items-center gap-1.5 text-[12px] text-blue-600 hover:opacity-70 border border-blue-600/30 rounded-md px-3 py-1.5 disabled:opacity-50">
              <Download size={12} />
              {downloading === r.id ? 'Downloading…' : 'Download'}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
