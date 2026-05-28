import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

interface Props {
  allow: number;
  deny: number;
  review: number;
}

export function DecisionDonut({ allow, deny, review }: Props) {
  const data = [
    { name: "Allow",  value: allow,  color: "#1D9E75" },
    { name: "Deny",   value: deny,   color: "#E24B4A" },
    { name: "Review", value: review, color: "#BA7517" },
  ].filter((d) => d.value > 0);

  return (
    <div className="bg-ac-card border border-ac-border rounded-[10px] p-4">
      <p className="text-[12px] font-medium text-ac-text-muted mb-3">Decision breakdown</p>
      <ResponsiveContainer width="100%" height={160}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            innerRadius={45}
            outerRadius={68}
            paddingAngle={2}
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value, name) => [value, name]}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E5E7EB" }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex justify-center gap-4 mt-1">
        {data.map((d) => (
          <div key={d.name} className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ background: d.color }} />
            <span className="text-[11px] text-ac-text-muted">{d.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
