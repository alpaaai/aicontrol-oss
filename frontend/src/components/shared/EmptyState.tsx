import { cn } from "@/lib/utils";

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ title, description, icon, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 p-12 rounded-lg border border-border",
        "bg-surface-raised text-center",
        className
      )}
    >
      {icon && <div className="text-text-muted">{icon}</div>}
      <div>
        <p className="text-sm font-medium text-text-primary">{title}</p>
        {description && <p className="text-xs text-text-muted mt-1">{description}</p>}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}
