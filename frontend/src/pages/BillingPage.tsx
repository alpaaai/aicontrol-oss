import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { getBillingUsage } from '../api/billing';
import type { BillingUsage } from '../api/billing';

const PLAN_LABELS: Record<string, string> = {
  community: 'Community',
  business: 'Business',
  enterprise: 'Enterprise',
};

const PLAN_COLORS: Record<string, string> = {
  community: 'bg-gray-100 text-gray-700',
  business: 'bg-blue-100 text-blue-700',
  enterprise: 'bg-purple-100 text-purple-700',
};

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

function formatCost(usd: number): string {
  if (usd === 0) return 'Free';
  return `$${usd.toFixed(2)}`;
}

export default function BillingPage() {
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBillingUsage()
      .then(setUsage)
      .catch(() => setError('Failed to load billing data.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-8 text-ac-text-muted animate-pulse">Loading billing data...</div>
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

  return (
    <div className="p-8 max-w-3xl space-y-8">

      {/* Plan header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ac-text-primary">
            Billing &amp; Subscription
          </h1>
          {usage.company && (
            <p className="text-ac-text-muted mt-1">{usage.company}</p>
          )}
        </div>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${PLAN_COLORS[usage.plan]}`}>
          {PLAN_LABELS[usage.plan]}
        </span>
      </div>

      {/* Plan details */}
      <div className="bg-ac-card border border-ac-border rounded-lg p-6 space-y-4">
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-ac-text-primary">
            {isCommunity ? 'Free' : `$${usage.monthly_base_usd}/mo`}
          </span>
          {!isCommunity && (
            <span className="text-ac-text-muted text-sm">
              + ${usage.rate_per_million}/million intercepts
            </span>
          )}
        </div>

        {usage.retention_days !== null && (
          <p className="text-sm text-amber-600">
            Audit log retention: {usage.retention_days} days.{' '}
            <span className="font-medium">Upgrade to Business for 1-year retention.</span>
          </p>
        )}

        <ul className="space-y-1">
          {usage.features.map((f) => (
            <li key={f} className="flex items-center gap-2 text-sm text-ac-text-primary">
              <span className="text-green-500">&#10003;</span> {f}
            </li>
          ))}
        </ul>

        {isCommunity ? (
          <button
            disabled
            className="mt-2 px-4 py-2 bg-ac-primary text-white rounded-md text-sm
                       opacity-50 cursor-not-allowed"
            title="Upgrade coming soon"
          >
            Upgrade to Business — $49/mo
          </button>
        ) : (
          <button
            disabled
            className="mt-2 px-4 py-2 border border-ac-border rounded-md text-sm
                       text-ac-text-muted opacity-50 cursor-not-allowed"
            title="Subscription management coming soon"
          >
            Manage Subscription
          </button>
        )}
        <p className="text-xs text-ac-text-muted">
          Self-serve subscription management coming soon. Contact{' '}
          <a href="mailto:enterprise@aictl.io" className="underline">
            enterprise@aictl.io
          </a>{' '}
          to change your plan.
        </p>
      </div>

      {/* Usage chart */}
      <div className="bg-ac-card border border-ac-border rounded-lg p-6 space-y-4">
        <h2 className="text-lg font-semibold text-ac-text-primary">Intercept Usage</h2>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-ac-text-muted uppercase tracking-wide">This month</p>
            <p className="text-2xl font-bold text-ac-text-primary">
              {formatNumber(usage.this_month.intercepts)}
            </p>
            <p className="text-sm text-ac-text-muted">
              {isCommunity
                ? 'Free'
                : `Est. ${formatCost(usage.this_month.estimated_cost_usd)}`}
            </p>
          </div>
          <div>
            <p className="text-xs text-ac-text-muted uppercase tracking-wide">Last month</p>
            <p className="text-2xl font-bold text-ac-text-primary">
              {formatNumber(usage.last_month.intercepts)}
            </p>
            <p className="text-sm text-ac-text-muted">
              {isCommunity
                ? 'Free'
                : `Est. ${formatCost(usage.last_month.estimated_cost_usd)}`}
            </p>
          </div>
        </div>

        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E9ECEF" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={(v) => formatNumber(v)} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(v) => [formatNumber(Number(v)), 'Intercepts']} />
            <Bar dataKey="intercepts" fill="#3B5BDB" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>

        <p className="text-xs text-ac-text-muted">
          {isCommunity
            ? 'Community: all intercepts are free. Upgrade for Slack HITL, longer retention, and compliance features.'
            : `Estimated cost = intercepts × $${usage.rate_per_million} per million. Final billing handled via Stripe (coming soon).`}
        </p>
      </div>

    </div>
  );
}
