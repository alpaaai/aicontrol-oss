import { useCallback, useState } from "react";
import { usePoll } from "@/hooks/usePoll";
import { getOutcomes } from "@/api/dashboard";
import { StatCard } from "./StatCard";
import { AgentOutcomeTable } from "./AgentOutcomeTable";
import { DecisionFeed } from "./DecisionFeed";
import { BaselineDialog } from "./BaselineDialog";

export function OverviewPage() {
  const fetcher = useCallback(() => getOutcomes("7d"), []);
  const { data, loading, error } = usePoll(fetcher, 30000);
  const [showBaselineDialog, setShowBaselineDialog] = useState(
    () => sessionStorage.getItem("show_baseline_dialog") === "true",
  );

  const closeBaselineDialog = () => {
    sessionStorage.removeItem("show_baseline_dialog");
    setShowBaselineDialog(false);
  };

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
      ) : error ? (
        <div className="text-center text-sm text-ac-error py-10">
          Couldn't load overview data. Try refreshing the page.
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

      {showBaselineDialog && <BaselineDialog onClose={closeBaselineDialog} />}
    </div>
  );
}
