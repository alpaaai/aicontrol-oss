import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { DecisionHour } from "@/api/dashboard";

interface Props {
  data: DecisionHour[];
  window: string;
  granularity: "hour" | "day";
}

export function DecisionTrendChart({ data, window, granularity }: Props) {
  // Keyed on the full ISO timestamp, never just a formatted "HH:mm" label --
  // that string repeats every day, and a same-hour bucket from an earlier day
  // would silently overwrite an earlier bucket's counts instead of getting
  // its own bar.
  const pivoted = data.reduce<Record<string, { at: number; counts: Record<string, number> }>>(
    (acc, d) => {
      const at = new Date(d.hour).getTime();
      acc[d.hour] = acc[d.hour] ?? { at, counts: {} };
      if (d.decision) {
        acc[d.hour].counts[d.decision] = d.count;
      }
      return acc;
    },
    {}
  );

  const labelFormat: Intl.DateTimeFormatOptions =
    granularity === "day"
      ? { month: "short", day: "numeric" }
      : window === "24h"
      ? { hour: "2-digit", minute: "2-digit", hour12: false }
      : { month: "short", day: "numeric", hour: "2-digit", hour12: false };

  const chartData = Object.values(pivoted)
    .sort((a, b) => a.at - b.at)
    .map(({ at, counts }) => ({
      hour: new Date(at).toLocaleString("en-US", labelFormat),
      allow: counts.allow ?? 0,
      deny: counts.deny ?? 0,
      review: counts.review ?? 0,
    }));

  return (
    <div className="bg-ac-surface-card border border-ac-hairline rounded-lg p-4">
      <p className="text-title-sm text-ac-ink mb-4">
        {granularity === "day" ? "Decisions by day" : "Decisions by hour"} — last {window}
      </p>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart
          data={chartData}
          margin={{ top: 0, right: 8, bottom: 0, left: 0 }}
        >
          <XAxis
            dataKey="hour"
            tick={{ fontSize: 10, fill: "var(--ac-muted-soft)" }}
            tickLine={false}
            axisLine={false}
            interval={window === "7d" ? 23 : 3}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "var(--ac-muted-soft)" }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              fontSize: 12,
              borderRadius: 8,
              border: "1px solid var(--ac-hairline)",
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="allow"  fill="var(--ac-decision-allow)"  radius={[3, 3, 0, 0]} maxBarSize={16} />
          <Bar dataKey="deny"   fill="var(--ac-decision-deny)"   radius={[3, 3, 0, 0]} maxBarSize={16} />
          <Bar dataKey="review" fill="var(--ac-decision-review)" radius={[3, 3, 0, 0]} maxBarSize={16} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
