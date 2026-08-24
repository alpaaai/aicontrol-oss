import { useCallback } from "react";
import { usePoll } from "@/hooks/usePoll";
import { getOutcomes } from "@/api/dashboard";
import { OutcomeSummary } from "./OutcomeSummary";
import { DecisionFeed } from "./DecisionFeed";

export function OverviewPage() {
  const fetcher = useCallback(() => getOutcomes("7d"), []);
  const { data, loading } = usePoll(fetcher, 30000);

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <h1 className="text-title-lg text-ac-ink">Overview</h1>
      {loading && !data ? (
        <div className="h-16 bg-ac-surface-sunk rounded-md animate-pulse" />
      ) : (
        <OutcomeSummary workflows={data?.workflows ?? []} />
      )}
      <DecisionFeed />
    </div>
  );
}
