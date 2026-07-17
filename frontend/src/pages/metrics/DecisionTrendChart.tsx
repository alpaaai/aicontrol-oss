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
}

export function DecisionTrendChart({ data }: Props) {
  const pivoted = data.reduce<Record<string, Record<string, number>>>(
    (acc, d) => {
      const h = new Date(d.hour).toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
      acc[h] = acc[h] ?? {};
      if (d.decision) {
        acc[h][d.decision] = d.count;
      }
      return acc;
    },
    {}
  );

  const chartData = Object.entries(pivoted)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([hour, counts]) => ({
      hour,
      allow: counts.allow ?? 0,
      deny: counts.deny ?? 0,
      review: counts.review ?? 0,
    }));

  return (
    <div className="bg-ac-card border border-ac-border rounded-lg shadow-ac-card p-4">
      <p className="text-[13px] font-medium text-ac-text-primary mb-4">
        Decisions by hour — last 24h
      </p>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart
          data={chartData}
          margin={{ top: 0, right: 8, bottom: 0, left: 0 }}
        >
          <defs>
            <linearGradient id="allowGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#34D399" />
              <stop offset="100%" stopColor="#0F7A54" />
            </linearGradient>
            <linearGradient id="denyGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#F87171" />
              <stop offset="100%" stopColor="#C22E28" />
            </linearGradient>
            <linearGradient id="reviewGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#FBBF24" />
              <stop offset="100%" stopColor="#8F5710" />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="hour"
            tick={{ fontSize: 10, fill: "#9CA3AF" }}
            tickLine={false}
            axisLine={false}
            interval={3}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "#9CA3AF" }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              fontSize: 12,
              borderRadius: 8,
              border: "1px solid #DDE9EC",
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="allow"  fill="url(#allowGrad)"  radius={[3, 3, 0, 0]} maxBarSize={16} />
          <Bar dataKey="deny"   fill="url(#denyGrad)"   radius={[3, 3, 0, 0]} maxBarSize={16} />
          <Bar dataKey="review" fill="url(#reviewGrad)" radius={[3, 3, 0, 0]} maxBarSize={16} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
