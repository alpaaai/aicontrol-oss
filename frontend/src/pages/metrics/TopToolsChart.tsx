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
}

export function TopToolsChart({ data }: Props) {
  return (
    <div className="bg-ac-card border border-ac-border rounded-[10px] p-4">
      <p className="text-[13px] font-medium text-ac-text-primary mb-4">
        Top tools — last 24h
      </p>
      <ResponsiveContainer width="100%" height={Math.max(220, data.length * 28)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
        >
          <XAxis
            type="number"
            tick={{ fontSize: 10, fill: "#9CA3AF" }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey="tool"
            interval={0}
            tick={{
              fontSize: 11,
              fill: "#4B5563",
              fontFamily: "Geist Mono, monospace",
            }}
            tickLine={false}
            axisLine={false}
            width={160}
          />
          <Tooltip
            contentStyle={{
              fontSize: 12,
              borderRadius: 8,
              border: "1px solid #E5E7EB",
            }}
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={14}>
            {data.map((_, i) => (
              <Cell key={i} fill="#3B5BDB" opacity={1 - i * 0.06} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
