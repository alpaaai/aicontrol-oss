import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { TopTool } from "@/api/dashboard";

interface Props {
  data: TopTool[];
  window: string;
}

export function TopToolsChart({ data, window }: Props) {
  return (
    <div className="bg-ac-surface-card border border-ac-hairline rounded-lg p-4">
      <p className="text-title-sm text-ac-ink mb-4">Top tools — last {window}</p>
      <ResponsiveContainer width="100%" height={Math.max(220, data.length * 28)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
        >
          <XAxis
            type="number"
            tick={{ fontSize: 10, fill: "var(--ac-muted-soft)" }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey="tool"
            interval={0}
            tick={{
              fontSize: 11,
              fill: "var(--ac-body)",
              fontFamily: "JetBrains Mono, monospace",
            }}
            tickLine={false}
            axisLine={false}
            width={160}
          />
          <Tooltip
            contentStyle={{
              fontSize: 12,
              borderRadius: 8,
              border: "1px solid var(--ac-hairline)",
            }}
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={14}>
            {data.map((_, i) => (
              <Cell key={i} fill="var(--ac-body-strong)" opacity={1 - i * 0.06} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
