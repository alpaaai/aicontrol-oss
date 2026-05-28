import { Lock } from "lucide-react";
import { cn } from "@/lib/utils";

interface EnterpriseLockProps {
  feature?: string;
  className?: string;
}

export function EnterpriseLock({ feature, className }: EnterpriseLockProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 p-8 rounded-lg border border-border",
        "bg-surface-raised text-text-secondary",
        className
      )}
    >
      <Lock className="w-8 h-8 text-text-muted" />
      <div className="text-center">
        <p className="text-sm font-medium text-text-primary">Enterprise Feature</p>
        {feature && (
          <p className="text-xs text-text-muted mt-1">{feature} requires an enterprise plan.</p>
        )}
      </div>
      <a
        href="mailto:sales@aicontrol.dev"
        className="text-xs text-brand hover:text-brand-light transition-colors"
      >
        Contact sales to upgrade
      </a>
    </div>
  );
}
