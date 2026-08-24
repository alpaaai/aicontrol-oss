import { useCallback } from "react";
import { usePoll } from "@/hooks/usePoll";
import { getSummary } from "@/api/dashboard";
import { getMetrics } from "@/api/metrics";
import { DecisionTrendChart } from "./DecisionTrendChart";
import { TopToolsChart } from "./TopToolsChart";
import { StatCard } from "@/pages/overview/StatCard";

export function MetricsPage() {
  const fetcher = useCallback(() => getSummary(), []);
  const { data, loading } = usePoll(fetcher, 30000);

  const metricsFetcher = useCallback(() => getMetrics(), []);
  const { data: metrics, loading: metricsLoading } = usePoll(metricsFetcher, 60000);

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-title-lg text-ac-ink">Decision metrics</h1>
      </div>

      <div className="flex gap-4 flex-wrap">
        <StatCard
          index={0}
          featured
          label="Intercepts (7 days)"
          value={loading ? "—" : (data?.intercepts_7d.toLocaleString() ?? "—")}
        />
        <StatCard
          index={1}
          label="Intercepts (30 days)"
          value={loading ? "—" : (data?.intercepts_30d.toLocaleString() ?? "—")}
        />
        <StatCard
          index={2}
          label="Active agents"
          value={loading ? "—" : (data?.active_agents ?? "—")}
        />
        <StatCard
          index={3}
          label="Active policies"
          value={loading ? "—" : (data?.active_policies ?? "—")}
        />
        <StatCard
          index={4}
          label="Policy hit rate (7d)"
          value={metricsLoading ? "—" : `${metrics?.policy_hit_rate ?? 0}%`}
        />
        <StatCard
          index={5}
          label="Avg review time"
          value={
            metricsLoading || metrics?.avg_review_seconds == null
              ? "—"
              : metrics.avg_review_seconds < 3600
              ? `${Math.round(metrics.avg_review_seconds / 60)}m`
              : `${Math.round(metrics.avg_review_seconds / 3600)}h`
          }
        />
      </div>

      {data && (
        <div className="grid grid-cols-2 gap-4">
          <DecisionTrendChart data={data.decisions_by_hour} />
          <TopToolsChart data={data.top_tools} />
        </div>
      )}

      {metrics && metrics.top_agents_by_deny_rate.length > 0 && (
        <div className="bg-ac-surface-card border border-ac-hairline rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-ac-hairline">
            <p className="text-title-sm text-ac-ink">Top agents by deny rate (7d)</p>
          </div>
          {metrics.top_agents_by_deny_rate.map((a) => (
            <div
              key={a.agent_name}
              className="flex items-center justify-between px-4 py-2.5 border-b border-ac-hairline-soft text-body-sm"
            >
              <span className="text-ac-ink">{a.agent_name}</span>
              <div className="flex items-center gap-4">
                <span className="text-ac-muted text-caption">{a.total} calls</span>
                <span
                  className={`font-medium ${
                    a.deny_rate > 20
                      ? "text-ac-error"
                      : a.deny_rate > 5
                      ? "text-ac-warning"
                      : "text-ac-ink"
                  }`}
                >
                  {a.deny_rate}% deny
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
