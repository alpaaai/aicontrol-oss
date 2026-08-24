interface TopBarProps {
  title: string;
}

export function TopBar({ title }: TopBarProps) {
  return (
    <div className="h-14 border-b border-ac-hairline flex items-center px-6 bg-ac-surface-card sticky top-0 z-10">
      <h1 className="text-[18px] font-semibold tracking-[-0.02em] text-ac-ink">{title}</h1>
    </div>
  );
}
