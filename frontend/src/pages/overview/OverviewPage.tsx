import { useCallback } from "react";
import { usePoll } from "@/hooks/usePoll";
import { getOutcomes } from "@/api/dashboard";
import { StatCard } from "./StatCard";
import { AgentOutcomeTable } from "./AgentOutcomeTable";
import { DecisionFeed } from "./DecisionFeed";

export function OverviewPage() {
  const fetcher = useCallback(() => getOutcomes("7d"), []);
  const { data, loading } = usePoll(fetcher, 30000);

  const agents = data?.agents ?? [];
  const totalCalls = agents.reduce((sum, a) => sum + a.calls, 0);
  const totalApprovalNeeded = agents.reduce((sum, a) => sum + a.held_for_approval, 0);
  const totalDenied = agents.reduce((sum, a) => sum + a.denied, 0);
  const activeAgents = agents.length;

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <h1 className="text-title-lg text-ac-ink">Overview</h1>

      {loading && !data ? (
        <div className="space-y-4">
          <div className="h-24 bg-ac-surface-sunk rounded-md animate-pulse" />
          <div className="h-64 bg-ac-surface-sunk rounded-md animate-pulse" />
        </div>
      ) : (
        <>
          <div className="flex gap-3">
            <StatCard
              label="Tool calls"
              value={totalCalls.toLocaleString()}
              index={0}
              featured
            />
            <StatCard label="Active agents" value={activeAgents} index={1} />
            <StatCard
              label="Approval Needed"
              value={totalApprovalNeeded}
              index={2}
            />
            <StatCard label="Denied" value={totalDenied} index={3} />
          </div>

          <AgentOutcomeTable agents={agents} />
        </>
      )}

      <DecisionFeed />
    </div>
  );
}
