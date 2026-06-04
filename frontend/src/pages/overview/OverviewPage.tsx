import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { usePoll } from "@/hooks/usePoll";
import { getSummary } from "@/api/dashboard";
import { StatCard } from "./StatCard";
import { LiveFeedTable } from "./LiveFeedTable";
import { DecisionDonut } from "./DecisionDonut";
import { InterceptSparkline } from "./InterceptSparkline";
import { SkeletonCard } from "@/components/shared/LoadingSkeleton";

export function OverviewPage() {
  const navigate = useNavigate();
  const fetcher = useCallback(() => getSummary(), []);
  const { data, loading } = usePoll(fetcher, 30000);

  return (
    <div className="p-6 space-y-5">
      <div className="animate-fade-up" style={{ animationDelay: "0ms" }}>
        <h2 className="text-[18px] font-semibold text-ac-text-primary">
          Dashboard
        </h2>
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
                data?.pending_reviews === 0
                  ? "Queue clear"
                  : data && data.overdue_reviews > 0
                  ? `${data.overdue_reviews} overdue`
                  : "Needs attention"
              }
            />
            {data && data.active_warnings > 0 && (
              <StatCard
                index={4}
                accentColor="#BA7517"
                label="Active warnings"
                value={data.active_warnings}
                delta="Policy drift detected"
                deltaPositive={false}
                onDeltaClick={() => navigate("/policies?tab=drift")}
              />
            )}
            {data && data.high_risk_sessions > 0 && (
              <StatCard
                index={5}
                accentColor="#E24B4A"
                label="High-risk sessions"
                value={data.high_risk_sessions}
                delta="risk > 50, last hour"
                deltaPositive={false}
              />
            )}
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
        {data?.top_denied_tool && (
          <p className="text-[12px] text-ac-text-muted mt-2">
            Most blocked tool today:{" "}
            <span className="font-medium text-ac-deny">{data.top_denied_tool.tool}</span>
            {" "}({data.top_denied_tool.count} denies)
          </p>
        )}
      </div>
    </div>
  );
}
