import { useState } from 'react'
import { generateReport } from '../../api/reports'
import type { Framework, ReportFormat } from '../../api/reports'
import { FileCheck } from 'lucide-react'

const FRAMEWORKS: { value: Framework; label: string }[] = [
  { value: 'eu_ai_act',   label: 'EU AI Act' },
  { value: 'nist_ai_rmf', label: 'NIST AI RMF' },
  { value: 'soc2',        label: 'SOC 2' },
  { value: 'iso_42001',   label: 'ISO 42001' },
]

interface Props { onGenerated: () => void }

function triggerDownload(blob: Blob, format: ReportFormat, dateFrom: string, dateTo: string) {
  const ext = format === 'both' ? 'zip' : format
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `aicontrol-compliance-${dateFrom}-${dateTo}.${ext}`
  a.click()
  URL.revokeObjectURL(url)
}

export function ReportForm({ onGenerated }: Props) {
  const today = new Date().toISOString().split('T')[0]
  const thirtyDaysAgo = new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0]

  const [dateFrom, setDateFrom] = useState(thirtyDaysAgo)
  const [dateTo, setDateTo] = useState(today)
  const [frameworks, setFrameworks] = useState<Framework[]>(['soc2'])
  const [format, setFormat] = useState<ReportFormat>('pdf')
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  const toggleFramework = (fw: Framework) => {
    setFrameworks(prev =>
      prev.includes(fw) ? prev.filter(f => f !== fw) : [...prev, fw]
    )
  }

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (frameworks.length === 0) { setError('Select at least one framework'); return }
    setGenerating(true); setError('')
    try {
      const blob = await generateReport({ date_from: dateFrom, date_to: dateTo, frameworks, format })
      triggerDownload(blob, format, dateFrom, dateTo)
      onGenerated()
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Generation failed. Check enterprise license.')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-[10px] p-5">
      <h3 className="text-[14px] font-semibold text-gray-900 mb-4">Generate Compliance Report</h3>
      <form onSubmit={handleGenerate} className="space-y-4">

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[12px] text-gray-500 block mb-1">From</label>
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/20" />
          </div>
          <div>
            <label className="text-[12px] text-gray-500 block mb-1">To</label>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/20" />
          </div>
        </div>

        <div>
          <label className="text-[12px] text-gray-500 block mb-2">Frameworks</label>
          <div className="flex flex-wrap gap-2">
            {FRAMEWORKS.map(fw => (
              <button key={fw.value} type="button"
                onClick={() => toggleFramework(fw.value)}
                className={`px-3 py-1.5 rounded-lg text-[12px] font-medium border transition-colors ${
                  frameworks.includes(fw.value)
                    ? 'bg-purple-600 text-white border-purple-600'
                    : 'border-gray-200 text-gray-600 hover:border-purple-400/40'
                }`}>
                {fw.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="text-[12px] text-gray-500 block mb-2">Format</label>
          <div className="flex gap-2">
            {(['pdf', 'md', 'both'] as ReportFormat[]).map(f => (
              <button key={f} type="button"
                onClick={() => setFormat(f)}
                className={`px-3 py-1.5 rounded-lg text-[12px] font-medium border transition-colors ${
                  format === f
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'border-gray-200 text-gray-600 hover:border-blue-400/40'
                }`}>
                {f === 'both' ? 'PDF + MD' : f.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {error && <p className="text-xs text-red-500">{error}</p>}

        <button type="submit" disabled={generating}
          className="flex items-center gap-2 bg-purple-600 text-white rounded-lg px-5 py-2.5 text-sm font-medium
                     hover:opacity-90 disabled:opacity-50 transition-opacity">
          <FileCheck size={14} />
          {generating ? 'Generating report…' : 'Generate report'}
        </button>
      </form>
    </div>
  )
}
