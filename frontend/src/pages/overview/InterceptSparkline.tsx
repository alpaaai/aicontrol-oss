import { AreaChart, Area, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import type { DecisionHour } from "@/api/dashboard";

interface Props {
  data: DecisionHour[];
}

export function InterceptSparkline({ data }: Props) {
  const byHour = data.reduce<Record<string, number>>((acc, d) => {
    acc[d.hour] = (acc[d.hour] ?? 0) + d.count;
    return acc;
  }, {});

  const chartData = Object.entries(byHour)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([hour, count]) => ({
      hour: new Date(hour).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      }),
      count,
    }));

  return (
    <div className="bg-ac-card border border-ac-border rounded-lg shadow-ac-card p-4">
      <p className="text-[12px] font-medium text-ac-text-muted mb-3">Intercepts — last 30 days</p>
      <ResponsiveContainer width="100%" height={100}>
        <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="peacockGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#0284A8" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#0284A8" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="hour"
            tick={{ fontSize: 10, fill: "#9CA3AF" }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <Area
            type="monotone"
            dataKey="count"
            stroke="#0284A8"
            strokeWidth={1.5}
            fill="url(#peacockGrad)"
            dot={false}
          />
          <Tooltip
            contentStyle={{ fontSize: 11, borderRadius: 8, border: "1px solid #DDE9EC" }}
            formatter={(v) => [v, "intercepts"]}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
