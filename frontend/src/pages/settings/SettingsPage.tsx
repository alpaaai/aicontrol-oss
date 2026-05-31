import { useAuth } from '../../hooks/useAuth'
import { useLicense } from '../../hooks/useLicense'

function SettingRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-50">
      <span className="text-[13px] text-gray-600">{label}</span>
      <span className={`text-[13px] text-gray-800 ${mono ? 'font-mono' : 'font-medium'}`}>{value}</span>
    </div>
  )
}

export function SettingsPage() {
  const { user } = useAuth()
  const { isEnterprise } = useLicense()

  return (
    <div className="p-6 max-w-2xl">
      <div className="mb-6 animate-fade-up">
        <h2 className="text-[18px] font-semibold text-ac-text-primary">Settings</h2>
        <p className="text-sm text-gray-400 mt-0.5">View and manage your account settings.</p>
      </div>

      {/* License */}
      <div className="bg-white border border-gray-200 rounded-[10px] px-4 mb-4">
        <p className="text-[12px] font-medium text-gray-500 uppercase tracking-wide py-2.5 border-b border-gray-50">
          License
        </p>
        <SettingRow label="Plan" value={isEnterprise ? 'Enterprise' : 'Community'} />
        <div className="flex items-center justify-between py-3 border-b border-gray-50">
          <span className="text-[13px] text-gray-600">Enterprise features</span>
          {isEnterprise ? (
            <span className="text-[13px] text-gray-800 font-medium">Active</span>
          ) : (
            <button
              disabled
              className="px-3 py-1 bg-ac-primary text-white rounded-md text-xs font-medium
                         opacity-50 cursor-not-allowed"
              title="Upgrade coming soon"
            >
              Upgrade
            </button>
          )}
        </div>
      </div>

      {/* Auth */}
      <div className="bg-white border border-gray-200 rounded-[10px] px-4 mb-4">
        <p className="text-[12px] font-medium text-gray-500 uppercase tracking-wide py-2.5 border-b border-gray-50">
          Authentication
        </p>
        <SettingRow label="Method" value="Email OTP (passwordless)" />
        <SettingRow label="Session duration" value="8 hours" />
      </div>

      {/* Current user */}
      <div className="bg-white border border-gray-200 rounded-[10px] px-4">
        <p className="text-[12px] font-medium text-gray-500 uppercase tracking-wide py-2.5 border-b border-gray-50">
          Current session
        </p>
        <SettingRow label="User email" value={user?.email ?? '—'} />
        <SettingRow label="Role" value={user?.role ?? '—'} />
      </div>
    </div>
  )
}
