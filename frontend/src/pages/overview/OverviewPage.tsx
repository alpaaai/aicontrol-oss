import { useCallback } from "react";
import { usePoll } from "@/hooks/usePoll";
import { getSummary } from "@/api/dashboard";
import { StatCard } from "./StatCard";
import { LiveFeedTable } from "./LiveFeedTable";
import { DecisionDonut } from "./DecisionDonut";
import { InterceptSparkline } from "./InterceptSparkline";
import { SkeletonCard } from "@/components/shared/LoadingSkeleton";

export function OverviewPage() {
  const fetcher = useCallback(() => getSummary(), []);
  const { data, loading } = usePoll(fetcher, 30000);

  return (
    <div className="p-6 space-y-5">
      <div className="animate-fade-up" style={{ animationDelay: "0ms" }}>
        <h2 className="text-[18px] font-semibold text-ac-text-primary">
          Overview
        </h2>
        <p className="text-sm text-ac-text-muted mt-0.5">
          Live activity · refreshes every 30s
        </p>
      </div>

      {/* Stat cards */}
      <div className="flex gap-4 flex-wrap">
        {loading && !data ? (
          <>
            {[...Array(4)].map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </>
        ) : (
          <>
            <StatCard
              index={0}
              accentColor="#3B5BDB"
              label="Intercepts today"
              value={data?.intercepts_today.toLocaleString() ?? "—"}
              live
            />
            <StatCard
              index={1}
              accentColor={data && data.deny_rate_today < 5 ? "#1D9E75" : "#E24B4A"}
              label="Deny rate"
              value={`${data?.deny_rate_today ?? 0}%`}
              deltaPositive={data ? data.deny_rate_today < 5 : undefined}
              delta={
                data
                  ? data.deny_rate_today < 5
                    ? "Within threshold"
                    : "↑ Above threshold"
                  : undefined
              }
            />
            <StatCard
              index={2}
              accentColor="#6B7280"
              label="Active sessions"
              value={data?.active_sessions ?? "—"}
              delta="last hour"
            />
            <StatCard
              index={3}
              accentColor={data?.pending_reviews === 0 ? "#1D9E75" : "#BA7517"}
              label="Pending reviews"
              value={data?.pending_reviews ?? "—"}
              deltaPositive={data ? data.pending_reviews === 0 : undefined}
              delta={
                data?.pending_reviews === 0 ? "Queue clear" : "Needs attention"
              }
            />
          </>
        )}
      </div>

      {/* Charts */}
      {data && (
        <div className="grid grid-cols-3 gap-4 animate-fade-up" style={{ animationDelay: "240ms" }}>
          <div className="col-span-2">
            <InterceptSparkline data={data.decisions_by_hour} />
          </div>
          <DecisionDonut
            allow={data.allow_count_today}
            deny={data.deny_count_today}
            review={data.review_count_today}
          />
        </div>
      )}

      {/* Live feed */}
      <div className="animate-fade-up" style={{ animationDelay: "320ms" }}>
        <LiveFeedTable />
      </div>
    </div>
  );
}
