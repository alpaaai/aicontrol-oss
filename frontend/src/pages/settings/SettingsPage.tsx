import { useEffect, useState } from 'react'
import { Copy, CheckCircle, UserPlus, X, Pencil } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'
import { useLicense } from '../../hooks/useLicense'
import { useOrgSettings } from '../../context/OrgSettingsContext'
import { updateOrgSettings } from '@/api/orgSettings'
import { listUsers } from '@/api/users'
import type { UserItem } from '@/api/users'
import {
  createUser,
  updateUser,
  deleteUser,
  regenerateInvite,
} from '@/api/userManagement'
import type { MagicLinkResult } from '@/api/userManagement'

const TIMEZONES = [
  "UTC",
  "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "America/Anchorage", "America/Honolulu", "America/Sao_Paulo", "America/Toronto",
  "America/Vancouver", "Europe/London", "Europe/Paris", "Europe/Berlin",
  "Europe/Amsterdam", "Europe/Stockholm", "Europe/Zurich", "Europe/Warsaw",
  "Europe/Helsinki", "Europe/Istanbul", "Europe/Moscow", "Asia/Dubai",
  "Asia/Kolkata", "Asia/Dhaka", "Asia/Bangkok", "Asia/Singapore",
  "Asia/Shanghai", "Asia/Tokyo", "Asia/Seoul", "Australia/Sydney",
  "Australia/Melbourne", "Pacific/Auckland",
]

function SettingRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-50">
      <span className="text-[13px] text-gray-600">{label}</span>
      <span className={`text-[13px] text-gray-800 ${mono ? 'font-mono' : 'font-medium'}`}>{value}</span>
    </div>
  )
}

function userStatus(u: UserItem): { label: string; color: string } {
  if (!u.password_set) return { label: 'Pending', color: 'text-amber-500' }
  if (!u.is_active) return { label: 'Inactive', color: 'text-red-500' }
  return { label: 'Active', color: 'text-green-600' }
}

// ---------------------------------------------------------------------------
// Magic link display — copy button follows CreateTokenDialog pattern
// ---------------------------------------------------------------------------
function MagicLinkDisplay({
  magicLink,
  email,
  onDone,
}: {
  magicLink: string
  email: string
  onDone: () => void
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(magicLink)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <>
      <div className="flex items-center gap-2 mb-3">
        <CheckCircle size={16} className="text-green-600" />
        <h3 className="text-[16px] font-semibold text-ac-text-primary">Invite link ready</h3>
      </div>
      <p className="text-sm text-ac-text-muted mb-1">
        Send this link to <span className="font-medium">{email}</span>. It expires in 24 hours.
      </p>
      <p className="text-xs text-ac-text-muted mb-3">This link will not be shown again after you close this dialog.</p>
      <div className="bg-gray-50 border border-ac-border rounded-lg px-3 py-2.5 flex items-center gap-2 mb-4">
        <code className="text-[11px] font-mono text-ac-text-primary flex-1 break-all">{magicLink}</code>
        <button
          onClick={handleCopy}
          className="text-ac-text-muted hover:text-ac-primary shrink-0"
          title="Copy link"
        >
          {copied ? (
            <CheckCircle size={14} className="text-green-600" />
          ) : (
            <Copy size={14} />
          )}
        </button>
      </div>
      <button
        onClick={onDone}
        className="w-full bg-ac-primary text-white rounded-lg py-2 text-sm font-medium"
      >
        Done
      </button>
    </>
  )
}

// ---------------------------------------------------------------------------
// Invite User modal
// ---------------------------------------------------------------------------
function InviteUserDialog({
  open,
  onClose,
  onInvited,
}: {
  open: boolean
  onClose: () => void
  onInvited: () => void
}) {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('analyst')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<MagicLinkResult | null>(null)

  const reset = () => {
    setFullName('')
    setEmail('')
    setRole('analyst')
    setSubmitting(false)
    setError('')
    setResult(null)
  }

  const handleClose = () => {
    reset()
    onClose()
  }

  const handleDone = () => {
    reset()
    onInvited()
    onClose()
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const res = await createUser(fullName, email, role)
      setResult(res)
      onInvited()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e?.response?.data?.detail ?? 'Failed to create user')
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-ac-card rounded-[12px] border border-ac-border w-full max-w-md p-6 shadow-xl">
        {!result ? (
          <>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[16px] font-semibold text-ac-text-primary">Invite User</h3>
              <button onClick={handleClose} className="text-ac-text-muted hover:text-ac-text-primary">
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-3">
              <div>
                <label className="text-[12px] text-ac-text-muted block mb-1">Full Name *</label>
                <input
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jane Smith"
                  className="w-full border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20"
                />
              </div>
              <div>
                <label className="text-[12px] text-ac-text-muted block mb-1">Email *</label>
                <input
                  required
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="jane@example.com"
                  className="w-full border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20"
                />
              </div>
              <div>
                <label className="text-[12px] text-ac-text-muted block mb-1">Role</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20"
                >
                  <option value="admin">admin</option>
                  <option value="analyst">analyst</option>
                  <option value="auditor">auditor</option>
                </select>
              </div>
              {error && <p className="text-xs text-red-500">{error}</p>}
              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={handleClose}
                  className="flex-1 border border-ac-border rounded-lg py-2 text-sm text-ac-text-muted hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 bg-ac-primary text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50"
                >
                  {submitting ? 'Sending…' : 'Send invite'}
                </button>
              </div>
            </form>
          </>
        ) : (
          <MagicLinkDisplay
            magicLink={result.magic_link}
            email={result.user.email}
            onDone={handleDone}
          />
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Resend invite modal
// ---------------------------------------------------------------------------
function ResendInviteDialog({
  userId,
  email,
  open,
  onClose,
}: {
  userId: string
  email: string
  open: boolean
  onClose: () => void
}) {
  const [result, setResult] = useState<MagicLinkResult | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    regenerateInvite(userId)
      .then(setResult)
      .catch((err: unknown) => {
        const e = err as { response?: { data?: { detail?: string } } }
        setError(e?.response?.data?.detail ?? 'Failed to regenerate invite')
      })
  }, [open, userId])

  const handleClose = () => {
    setResult(null)
    setError('')
    onClose()
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-ac-card rounded-[12px] border border-ac-border w-full max-w-md p-6 shadow-xl">
        {error ? (
          <>
            <p className="text-sm text-red-500 mb-4">{error}</p>
            <button onClick={handleClose} className="w-full border border-ac-border rounded-lg py-2 text-sm">Close</button>
          </>
        ) : result ? (
          <MagicLinkDisplay magicLink={result.magic_link} email={email} onDone={handleClose} />
        ) : (
          <p className="text-sm text-ac-text-muted">Generating new invite link…</p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Delete confirmation dialog
// ---------------------------------------------------------------------------
function DeleteConfirmDialog({
  user,
  open,
  onClose,
  onDeleted,
}: {
  user: UserItem | null
  open: boolean
  onClose: () => void
  onDeleted: () => void
}) {
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')

  const handleDelete = async () => {
    if (!user) return
    setDeleting(true)
    try {
      await deleteUser(user.id)
      onDeleted()
      onClose()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e?.response?.data?.detail ?? 'Failed to delete user')
    } finally {
      setDeleting(false)
    }
  }

  if (!open || !user) return null

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-ac-card rounded-[12px] border border-ac-border w-full max-w-sm p-6 shadow-xl">
        <h3 className="text-[16px] font-semibold text-ac-text-primary mb-2">Delete user?</h3>
        <p className="text-sm text-ac-text-muted mb-4">
          This will permanently remove <span className="font-medium">{user.email}</span>. This cannot be undone.
        </p>
        {error && <p className="text-xs text-red-500 mb-3">{error}</p>}
        <div className="flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 border border-ac-border rounded-lg py-2 text-sm text-ac-text-muted hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="flex-1 bg-red-500 text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50 hover:bg-red-600"
          >
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Organization section
// ---------------------------------------------------------------------------
function OrgSection({ isAdmin }: { isAdmin: boolean }) {
  const { orgName, timezone, refresh } = useOrgSettings()
  const [editing, setEditing] = useState(false)
  const [nameInput, setNameInput] = useState('')
  const [tzInput, setTzInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const startEdit = () => {
    setNameInput(orgName)
    setTzInput(timezone)
    setError('')
    setEditing(true)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await updateOrgSettings({ org_name: nameInput, timezone: tzInput })
      refresh()
      setEditing(false)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e?.response?.data?.detail ?? 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-ac-card border border-ac-border rounded-lg shadow-ac-card px-4 mt-4">
      <div className="flex items-center justify-between py-2.5 border-b border-gray-50">
        <p className="text-[12px] font-medium text-gray-500 uppercase tracking-wide">Organization</p>
        {isAdmin && !editing && (
          <button
            onClick={startEdit}
            className="flex items-center gap-1 text-[11px] text-ac-primary hover:underline"
          >
            <Pencil size={11} />
            Edit
          </button>
        )}
      </div>

      {editing ? (
        <form onSubmit={handleSave} className="py-3 space-y-3">
          <div>
            <label className="text-[12px] text-gray-500 block mb-1">Organization name</label>
            <input
              required
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              className="w-full border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20"
            />
          </div>
          <div>
            <label className="text-[12px] text-gray-500 block mb-1">Timezone</label>
            <select
              value={tzInput}
              onChange={(e) => setTzInput(e.target.value)}
              className="w-full border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 bg-white"
            >
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>{tz}</option>
              ))}
            </select>
          </div>
          {error && <p className="text-xs text-red-500">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="flex-1 border border-ac-border rounded-lg py-2 text-sm text-ac-text-muted hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 bg-ac-primary text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      ) : (
        <>
          <div className="flex items-center justify-between py-3 border-b border-gray-50">
            <span className="text-[13px] text-gray-600">Name</span>
            <span className="text-[13px] text-gray-800 font-medium">{orgName || '—'}</span>
          </div>
          <div className="flex items-center justify-between py-3">
            <span className="text-[13px] text-gray-600">Timezone</span>
            <span className="text-[13px] text-gray-800 font-medium">{timezone}</span>
          </div>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Users section
// ---------------------------------------------------------------------------
function UsersSection({ currentUserId }: { currentUserId: string | undefined }) {
  const [users, setUsers] = useState<UserItem[]>([])
  const [loading, setLoading] = useState(true)
  const [inviteOpen, setInviteOpen] = useState(false)
  const [resendTarget, setResendTarget] = useState<UserItem | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<UserItem | null>(null)
  const [actionErrors, setActionErrors] = useState<Record<string, string>>({})

  const reload = () => {
    listUsers()
      .then(setUsers)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { reload() }, [])

  const toggleActive = async (u: UserItem) => {
    try {
      await updateUser(u.id, { is_active: !u.is_active })
      reload()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setActionErrors((prev) => ({ ...prev, [u.id]: e?.response?.data?.detail ?? 'Action failed' }))
    }
  }

  return (
    <div className="bg-ac-card border border-ac-border rounded-lg shadow-ac-card px-4 mt-4">
      <div className="flex items-center justify-between py-2.5 border-b border-gray-50">
        <p className="text-[12px] font-medium text-gray-500 uppercase tracking-wide">
          Users {!loading && `(${users.length})`}
        </p>
        <button
          onClick={() => setInviteOpen(true)}
          className="flex items-center gap-1 px-2.5 py-1 bg-ac-primary text-white rounded-md text-[11px] font-medium hover:bg-ac-primary/90"
        >
          <UserPlus size={12} />
          Invite User
        </button>
      </div>

      {loading ? (
        <p className="text-[13px] text-gray-400 py-4 text-center">Loading…</p>
      ) : users.length === 0 ? (
        <p className="text-[13px] text-gray-400 py-4 text-center">No users yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="text-[11px] text-gray-400 uppercase tracking-wide">
                <th className="py-2 pr-3 font-medium">Name / Email</th>
                <th className="py-2 pr-3 font-medium">Role</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Last Login</th>
                <th className="py-2 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const status = userStatus(u)
                return (
                  <tr key={u.id} className="border-t border-gray-50">
                    <td className="py-2.5 pr-3">
                      <p className="text-[13px] text-gray-800 font-medium">{u.name ?? '—'}</p>
                      <p className="text-[11px] text-gray-400">{u.email}</p>
                      {u.id === currentUserId && (
                        <span className="text-[10px] text-ac-primary font-medium">you</span>
                      )}
                    </td>
                    <td className="py-2.5 pr-3">
                      <span className="text-[11px] font-mono bg-gray-100 px-2 py-0.5 rounded text-gray-600">
                        {u.role}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3">
                      <span className={`text-[12px] font-medium ${status.color}`}>{status.label}</span>
                    </td>
                    <td className="py-2.5 pr-3 text-[12px] text-gray-500">
                      {u.last_login ? new Date(u.last_login).toLocaleDateString() : '—'}
                    </td>
                    <td className="py-2.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {!u.password_set && (
                          <button
                            onClick={() => setResendTarget(u)}
                            className="text-[11px] text-amber-600 hover:underline"
                          >
                            Resend Invite
                          </button>
                        )}
                        {u.password_set && u.is_active && (
                          <button
                            onClick={() => setResendTarget(u)}
                            className="text-[11px] text-ac-primary hover:underline"
                          >
                            Reset Password
                          </button>
                        )}
                        {u.password_set && (
                          <button
                            onClick={() => toggleActive(u)}
                            className={`text-[11px] hover:underline ${u.is_active ? 'text-gray-500' : 'text-green-600'}`}
                          >
                            {u.is_active ? 'Deactivate' : 'Reactivate'}
                          </button>
                        )}
                        {!u.is_root && (
                          <button
                            onClick={() => setDeleteTarget(u)}
                            className="text-[11px] text-red-500 hover:underline"
                          >
                            Delete
                          </button>
                        )}
                      </div>
                      {actionErrors[u.id] && (
                        <p className="text-[10px] text-red-500 mt-0.5">{actionErrors[u.id]}</p>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <InviteUserDialog
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        onInvited={reload}
      />
      <ResendInviteDialog
        userId={resendTarget?.id ?? ''}
        email={resendTarget?.email ?? ''}
        open={!!resendTarget}
        onClose={() => setResendTarget(null)}
      />
      <DeleteConfirmDialog
        user={deleteTarget}
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onDeleted={reload}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export function SettingsPage() {
  const { user } = useAuth()
  const { isEnterprise } = useLicense()

  return (
    <div className="p-6 max-w-3xl">
      <div className="mb-6 animate-fade-up">
        <h2 className="text-[18px] font-semibold text-ac-text-primary">Settings</h2>
        <p className="text-sm text-gray-400 mt-0.5">View and manage your account settings.</p>
      </div>

      {/* License */}
      <div className="bg-ac-card border border-ac-border rounded-lg shadow-ac-card px-4 mb-4">
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
      <div className="bg-ac-card border border-ac-border rounded-lg shadow-ac-card px-4 mb-4">
        <p className="text-[12px] font-medium text-gray-500 uppercase tracking-wide py-2.5 border-b border-gray-50">
          Authentication
        </p>
        <SettingRow label="Method" value="Email + Password" />
        <SettingRow label="Session duration" value="8 hours" />
      </div>

      {/* Current user */}
      <div className="bg-ac-card border border-ac-border rounded-lg shadow-ac-card px-4 mb-4">
        <p className="text-[12px] font-medium text-gray-500 uppercase tracking-wide py-2.5 border-b border-gray-50">
          Current session
        </p>
        <SettingRow label="User email" value={user?.email ?? '—'} />
        <SettingRow label="Role" value={user?.role ?? '—'} />
      </div>

      {/* Organization */}
      <OrgSection isAdmin={user?.role === 'admin'} />

      {/* Users (admin only) */}
      {user?.role === 'admin' && <UsersSection currentUserId={user?.id} />}
    </div>
  )
}
