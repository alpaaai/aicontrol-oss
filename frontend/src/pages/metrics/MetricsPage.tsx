import { useCallback } from "react";
import { usePoll } from "@/hooks/usePoll";
import { getSummary } from "@/api/dashboard";
import { DecisionTrendChart } from "./DecisionTrendChart";
import { TopToolsChart } from "./TopToolsChart";
import { StatCard } from "@/pages/overview/StatCard";

export function MetricsPage() {
  const fetcher = useCallback(() => getSummary(), []);
  const { data, loading } = usePoll(fetcher, 30000);

  return (
    <div className="p-6 space-y-5">
      <div className="animate-fade-up">
        <h2 className="text-[18px] font-semibold text-ac-text-primary">
          Decision Metrics
        </h2>
        <p className="text-sm text-ac-text-muted mt-0.5">Updates every 30s</p>
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
      </div>

      {data && (
        <div className="grid grid-cols-2 gap-4">
          <DecisionTrendChart data={data.decisions_by_hour} />
          <TopToolsChart data={data.top_tools} />
        </div>
      )}
    </div>
  );
}
