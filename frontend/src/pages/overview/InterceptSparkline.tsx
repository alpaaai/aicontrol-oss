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
      hour: new Date(hour).toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }),
      count,
    }));

  return (
    <div className="bg-ac-card border border-ac-border rounded-[10px] p-4">
      <p className="text-[12px] font-medium text-ac-text-muted mb-3">Intercepts — last 24h</p>
      <ResponsiveContainer width="100%" height={100}>
        <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="blueGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3B5BDB" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#3B5BDB" stopOpacity={0} />
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
            stroke="#3B5BDB"
            strokeWidth={1.5}
            fill="url(#blueGrad)"
            dot={false}
          />
          <Tooltip
            contentStyle={{ fontSize: 11, borderRadius: 8, border: "1px solid #E5E7EB" }}
            formatter={(v) => [v, "intercepts"]}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
