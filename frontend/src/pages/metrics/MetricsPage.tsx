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
      <div className="animate-fade-up">
        <h2 className="text-[18px] font-semibold text-ac-text-primary">
          Decision metrics
        </h2>
      </div>

      <div className="flex gap-4 flex-wrap">
        <StatCard
          index={0}
          accentColor="#3B5BDB"
          label="Intercepts (7 days)"
          value={loading ? "—" : (data?.intercepts_7d.toLocaleString() ?? "—")}
        />
        <StatCard
          index={1}
          accentColor="#534AB7"
          label="Intercepts (30 days)"
          value={loading ? "—" : (data?.intercepts_30d.toLocaleString() ?? "—")}
        />
        <StatCard
          index={2}
          accentColor="#1D9E75"
          label="Active agents"
          value={loading ? "—" : (data?.active_agents ?? "—")}
        />
        <StatCard
          index={3}
          accentColor="#BA7517"
          label="Active policies"
          value={loading ? "—" : (data?.active_policies ?? "—")}
        />
        <StatCard
          index={4}
          accentColor="#1D9E75"
          label="Policy hit rate (7d)"
          value={metricsLoading ? "—" : `${metrics?.policy_hit_rate ?? 0}%`}
        />
        <StatCard
          index={5}
          accentColor="#534AB7"
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
        <div className="bg-ac-card border border-ac-border rounded-[10px] overflow-hidden">
          <div className="px-4 py-3 border-b border-ac-border">
            <p className="text-[13px] font-semibold text-ac-text-primary">
              Top agents by deny rate (7d)
            </p>
          </div>
          {metrics.top_agents_by_deny_rate.map((a) => (
            <div
              key={a.agent_name}
              className="flex items-center justify-between px-4 py-2.5 border-b border-gray-50 text-[13px]"
            >
              <span className="text-ac-text-primary">{a.agent_name}</span>
              <div className="flex items-center gap-4">
                <span className="text-ac-text-muted text-[12px]">
                  {a.total} calls
                </span>
                <span
                  className={`font-medium ${
                    a.deny_rate > 20
                      ? "text-red-500"
                      : a.deny_rate > 5
                      ? "text-amber-500"
                      : "text-ac-text-primary"
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
