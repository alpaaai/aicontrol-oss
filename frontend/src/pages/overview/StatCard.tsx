interface StatCardProps {
  label: string;
  value: string | number;
  delta?: string;
  deltaPositive?: boolean;
  onDeltaClick?: () => void;
  live?: boolean;
  index?: number;
  featured?: boolean;
}

export function StatCard({ label, value, delta, deltaPositive, onDeltaClick, live, index = 0, featured }: StatCardProps) {
  return (
    <div
      className="bg-ac-surface-card border border-ac-hairline rounded-lg p-4 flex-1 min-w-[140px] relative overflow-hidden"
      style={{ animationDelay: `${index * 70}ms` }}
    >
      {featured && <div className="absolute left-0 right-0 top-0 h-[3px] bg-ac-primary" />}

      <div className="flex items-center gap-1.5 mb-2">
        {live && (
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-ac-decision-allow opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-ac-decision-allow" />
          </span>
        )}
        <p className="text-caption text-ac-muted">{label}</p>
      </div>
      <p className="text-display-sm text-ac-ink tabular-nums font-display">{value}</p>
      {delta && (
        onDeltaClick ? (
          <button
            onClick={onDeltaClick}
            className={`text-caption mt-1 underline underline-offset-2 cursor-pointer text-left ${
              deltaPositive === true ? "text-ac-decision-allow" : deltaPositive === false ? "text-ac-decision-deny" : "text-ac-muted"
            }`}
          >
            {delta}
          </button>
        ) : (
          <p
            className={`text-caption mt-1 ${
              deltaPositive === true ? "text-ac-decision-allow" : deltaPositive === false ? "text-ac-decision-deny" : "text-ac-muted"
            }`}
          >
            {delta}
          </p>
        )
      )}
    </div>
  );
}
