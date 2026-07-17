import { Lock } from "lucide-react";

interface EnterpriseLockProps {
  title: string;
  description: string;
  children?: React.ReactNode;
}

export function EnterpriseLock({ title, description, children }: EnterpriseLockProps) {
  return (
    <div className="relative rounded-lg border border-ac-border bg-ac-card shadow-ac-card overflow-hidden">
      {/* Blurred preview */}
      <div className="blur-sm pointer-events-none select-none opacity-40 p-5">
        {children ?? (
          <div className="space-y-2">
            <div className="h-4 bg-gray-200 rounded w-3/4" />
            <div className="h-4 bg-gray-200 rounded w-1/2" />
            <div className="h-4 bg-gray-200 rounded w-2/3" />
          </div>
        )}
      </div>
      {/* Lock overlay */}
      <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/60 backdrop-blur-[1px]">
        <div className="bg-ac-enterprise-bg border border-ac-enterprise/20 rounded-lg px-4 py-3 text-center max-w-xs">
          <Lock className="w-4 h-4 text-ac-enterprise mx-auto mb-1.5" />
          <p className="text-xs font-medium text-ac-enterprise">{title}</p>
          <p className="text-xs text-ac-text-muted mt-0.5">{description}</p>
        </div>
      </div>
    </div>
  );
}
