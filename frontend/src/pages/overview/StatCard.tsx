interface StatCardProps {
  label: string;
  value: string | number;
  delta?: string;
  deltaPositive?: boolean;
  live?: boolean;
}

export function StatCard({ label, value, delta, deltaPositive, live }: StatCardProps) {
  return (
    <div className="bg-ac-card border border-ac-border rounded-[10px] p-4 flex-1 min-w-[140px]">
      <div className="flex items-center gap-1.5 mb-2">
        {live && (
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-ac-allow opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-ac-allow" />
          </span>
        )}
        <p className="text-xs text-ac-text-muted">{label}</p>
      </div>
      <p className="text-[26px] font-semibold tracking-[-0.03em] text-ac-text-primary tabular-nums">
        {value}
      </p>
      {delta && (
        <p
          className={`text-[11px] mt-1 ${
            deltaPositive === true
              ? "text-ac-allow"
              : deltaPositive === false
              ? "text-ac-deny"
              : "text-ac-text-muted"
          }`}
        >
          {delta}
        </p>
      )}
    </div>
  );
}
