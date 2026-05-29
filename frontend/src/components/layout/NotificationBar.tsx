import { useEffect, useState } from 'react'
import { getSummary } from '../../api/dashboard'
import { listWarnings } from '../../api/warnings'
import { AlertTriangle, Clock, CheckCircle, X } from 'lucide-react'
import { useLicense } from '../../hooks/useLicense'

interface Notification {
  id: string
  type: 'warning' | 'review' | 'info'
  message: string
}

export function NotificationBar() {
  const { isEnterprise } = useLicense()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())

  useEffect(() => {
    const items: Notification[] = []

    getSummary().then(data => {
      if (data.pending_reviews > 0) {
        items.push({
          id: 'pending_reviews',
          type: 'review',
          message: `${data.pending_reviews} session${data.pending_reviews > 1 ? 's' : ''} pending review`,
        })
      }
      if (data.deny_rate_today > 10) {
        items.push({
          id: 'deny_rate',
          type: 'warning',
          message: `Deny rate today is ${data.deny_rate_today}% — above normal threshold`,
        })
      }
      setNotifications(prev => {
        const ids = new Set(prev.map(n => n.id))
        return [...prev, ...items.filter(n => !ids.has(n.id))]
      })
    }).catch(() => {})

    if (isEnterprise) {
      // listWarnings returns PolicyWarning[] directly
      listWarnings(true).then(warnings => {
        if (warnings.length > 0) {
          setNotifications(prev => {
            if (prev.some(n => n.id === 'drift_warnings')) return prev
            return [...prev, {
              id: 'drift_warnings',
              type: 'warning',
              message: `${warnings.length} active policy drift warning${warnings.length > 1 ? 's' : ''}`,
            }]
          })
        }
      }).catch(() => {})
    }
  }, [isEnterprise])

  const visible = notifications.filter(n => !dismissed.has(n.id))
  if (visible.length === 0) return null

  const icons = {
    warning: <AlertTriangle size={13} className="text-amber-500" />,
    review:  <Clock size={13} className="text-amber-500" />,
    info:    <CheckCircle size={13} className="text-green-600" />,
  }

  const colors = {
    warning: 'bg-amber-50 border-amber-100 text-amber-700',
    review:  'bg-amber-50 border-amber-100 text-amber-700',
    info:    'bg-green-50 border-green-100 text-green-700',
  }

  return (
    <div className="border-b border-gray-200 bg-white">
      {visible.map(n => (
        <div key={n.id}
          className={`flex items-center gap-2 px-6 py-2 text-[12px] border-b ${colors[n.type]}`}>
          {icons[n.type]}
          <span>{n.message}</span>
          <button
            onClick={() => setDismissed(prev => new Set([...prev, n.id]))}
            className="ml-auto opacity-50 hover:opacity-100">
            <X size={11} />
          </button>
        </div>
      ))}
    </div>
  )
}
