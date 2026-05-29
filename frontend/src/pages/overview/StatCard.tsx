interface StatCardProps {
  label: string;
  value: string | number;
  delta?: string;
  deltaPositive?: boolean;
  live?: boolean;
  index?: number;
  accentColor?: string;
}

export function StatCard({ label, value, delta, deltaPositive, live, index = 0, accentColor }: StatCardProps) {
  return (
    <div
      className="bg-ac-card border border-ac-border rounded-[10px] p-4 flex-1 min-w-[140px] animate-fade-up transition-shadow duration-200 hover:shadow-md relative overflow-hidden"
      style={{ animationDelay: `${index * 70}ms` }}
    >
      {/* Colored left-border accent */}
      {accentColor && (
        <div
          className="absolute left-0 top-3 bottom-3 w-[3px] rounded-r-full"
          style={{ background: accentColor }}
        />
      )}

      <div className="flex items-center gap-1.5 mb-2">
        {live && (
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-ac-allow opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-ac-allow" />
          </span>
        )}
        <p className="text-xs text-ac-text-muted">{label}</p>
      </div>
      <p className="text-[26px] font-semibold tracking-[-0.03em] text-ac-text-primary tabular-nums font-display">
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
