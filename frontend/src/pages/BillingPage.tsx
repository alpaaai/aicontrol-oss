import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { getBillingUsage, activateLicense } from '../api/billing';
import type { BillingUsage } from '../api/billing';
import { ReactivateBanner } from '../components/shared/ReactivateBanner';

const PLAN_PILL: Record<string, string> = {
  community: 'bg-violet-50 text-violet-700 border border-violet-200',
  business:  'bg-sky-50 text-sky-700 border border-sky-200',
  enterprise: 'bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-200',
  trial: 'bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-200',
};

const LICENSE_STATUS_LABEL: Record<string, string> = {
  active: 'Active',
  past_due: 'Past due',
  canceled: 'Canceled',
  unreachable: 'Unreachable',
  expired: 'Trial expired',
};

const UPGRADE_URL = 'https://aictl.io/pricing';

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

function formatSyncedAt(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

function PlanPill({ plan }: { plan: string }) {
  const cls = PLAN_PILL[plan] ?? PLAN_PILL.community;
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {plan.toUpperCase()}
    </span>
  );
}

export default function BillingPage() {
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activationCode, setActivationCode] = useState('');
  const [activating, setActivating] = useState(false);
  const [activationError, setActivationError] = useState<string | null>(null);
  const [activationSuccess, setActivationSuccess] = useState(false);

  const reload = () => {
    setLoading(true);
    getBillingUsage()
      .then(setUsage)
      .catch(() => setError('Failed to load billing data.'))
      .finally(() => setLoading(false));
  };

  useEffect(reload, []);

  const handleActivate = async () => {
    setActivating(true);
    setActivationError(null);
    setActivationSuccess(false);
    try {
      await activateLicense(activationCode);
      setActivationSuccess(true);
      reload();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to activate license.';
      setActivationError(detail);
    } finally {
      setActivating(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-ac-muted animate-pulse">Loading billing data...</div>
    );
  }

  if (error || !usage) {
    return (
      <div className="p-8 text-red-500">{error ?? 'No data available.'}</div>
    );
  }

  const chartData = [
    {
      name: usage.last_month.period,
      intercepts: usage.last_month.intercepts,
      label: 'Last month',
    },
    {
      name: usage.this_month.period,
      intercepts: usage.this_month.intercepts,
      label: 'This month',
    },
  ];

  const isCommunity = usage.plan === 'community';
  const needsReactivation =
    usage.license_status === 'past_due' ||
    usage.license_status === 'canceled' ||
    usage.license_status === 'unreachable';

  return (
    <div className="p-8 max-w-3xl space-y-8">

      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ac-ink">
            Subscription and usage
          </h1>
          {usage.company && (
            <p className="text-ac-muted mt-1">{usage.company}</p>
          )}
        </div>
        {isCommunity && (
          <a
            href={UPGRADE_URL}
            target="_blank"
            rel="noreferrer"
            className="px-4 py-2 bg-ac-primary hover:opacity-90 text-white rounded-md text-sm"
          >
            Upgrade
          </a>
        )}
      </div>

      {/* Plan details */}
      <div className="bg-ac-surface-card border border-ac-hairline rounded-lg p-6 space-y-4">
        <div className="flex items-center gap-3">
          <PlanPill plan={usage.plan} />
          {usage.license_status && (
            <span className="text-sm text-ac-muted">
              {LICENSE_STATUS_LABEL[usage.license_status] ?? usage.license_status}
            </span>
          )}
        </div>

        {usage.license_synced_at && (
          <p className="text-xs text-ac-muted">
            Last synced {formatSyncedAt(usage.license_synced_at)}
          </p>
        )}

        {usage.plan === 'community' && usage.retention_days !== null && (
          <p className="text-sm text-amber-600">
            Audit log retention: {usage.retention_days} days.{' '}
            <span className="font-medium">Upgrade to Business for 30-day retention.</span>
          </p>
        )}

        {usage.plan !== 'community' && usage.retention_days !== null && (
          <p className="text-sm text-ac-muted">
            Audit log retention: {usage.retention_days} days.
          </p>
        )}

        <ul className="space-y-1">
          {usage.features.map((f) => (
            <li key={f} className="flex items-center gap-2 text-sm text-ac-ink">
              <span className="text-green-500">&#10003;</span> {f}
            </li>
          ))}
        </ul>

        <div className="flex gap-2">
          {!isCommunity && usage.manage_subscription_url && (
            <a
              href={usage.manage_subscription_url}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-flex px-4 py-2 border border-ac-hairline rounded-md text-sm
                         text-ac-ink hover:bg-ac-surface-sunk"
            >
              Manage Subscription
            </a>
          )}

          {usage.plan === 'trial' && usage.upgrade_url && (
            <a
              href={usage.upgrade_url}
              className="mt-2 inline-flex px-4 py-2 bg-ac-primary hover:opacity-90 text-white rounded-md text-sm"
            >
              Upgrade to Business
            </a>
          )}
        </div>

        {!isCommunity && !usage.manage_subscription_url && (
          <p className="text-xs text-ac-muted">
            Self-serve subscription management unavailable for this plan. Contact{' '}
            <a href="mailto:hello@aictl.io" className="underline">
              hello@aictl.io
            </a>{' '}
            to change your plan.
          </p>
        )}

        {/* Activation code entry */}
        <div className="pt-4 border-t border-ac-hairline space-y-2">
          <label htmlFor="activation-code" className="block text-sm font-medium text-ac-ink">
            Activation code
          </label>
          <div className="flex gap-2">
            <input
              id="activation-code"
              type="text"
              placeholder="Activation code"
              value={activationCode}
              onChange={(e) => setActivationCode(e.target.value)}
              className="flex-1 px-3 py-2 border border-ac-hairline rounded-md text-sm"
            />
            <button
              onClick={handleActivate}
              disabled={activating || !activationCode}
              className="px-4 py-2 bg-ac-primary text-white rounded-md text-sm disabled:opacity-50"
            >
              {activating ? 'Activating…' : 'Activate'}
            </button>
          </div>
          {activationError && (
            <p className="text-sm text-red-500">{activationError}</p>
          )}
          {activationSuccess && (
            <p className="text-sm text-green-600">License activated.</p>
          )}
          <p className="text-xs text-ac-muted">
            Received a code by email after checkout? Enter it here to activate your plan.
          </p>
        </div>
      </div>

      {/* Usage chart / reactivate prompt */}
      {needsReactivation ? (
        <ReactivateBanner manageSubscriptionUrl={usage.manage_subscription_url} />
      ) : (
        <div className="bg-ac-surface-card border border-ac-hairline rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold text-ac-ink">Intercept Usage</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-ac-muted uppercase tracking-wide">This month</p>
              <p className="text-2xl font-bold text-ac-ink">
                {formatNumber(usage.this_month.intercepts)}
              </p>
            </div>
            <div>
              <p className="text-xs text-ac-muted uppercase tracking-wide">Last month</p>
              <p className="text-2xl font-bold text-ac-ink">
                {formatNumber(usage.last_month.intercepts)}
              </p>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E9ECEF" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={(v) => formatNumber(v)} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v) => [formatNumber(Number(v)), 'Intercepts']} />
              <Bar dataKey="intercepts" fill="#0284A8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>

          {isCommunity && (
            <p className="text-xs text-ac-muted">
              Upgrade for Slack HITL, longer retention, and compliance features.
            </p>
          )}
        </div>
      )}

    </div>
  );
}
