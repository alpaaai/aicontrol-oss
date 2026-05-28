import { useCallback } from "react";
import { usePoll } from "@/hooks/usePoll";
import { listAuditEvents } from "@/api/auditEvents";
import type { AuditEvent } from "@/api/auditEvents";
import { DecisionBadge } from "@/components/shared/DecisionBadge";

export function LiveFeedTable() {
  const fetcher = useCallback(() => listAuditEvents({ limit: 20 }), []);
  const { data, loading } = usePoll(fetcher, 4000);

  return (
    <div className="bg-ac-card border border-ac-border rounded-[10px] p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-ac-allow opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-ac-allow" />
        </span>
        <p className="text-[12px] font-medium text-ac-text-muted">Live intercepts</p>
        <p className="ml-auto text-[11px] text-ac-text-muted">updates every 4s</p>
      </div>

      {loading && !data ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-8 bg-gray-50 rounded animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="divide-y divide-gray-50">
          {data?.events.map((event: AuditEvent) => (
            <div key={event.id} className="flex items-center gap-3 py-2 text-[12px]">
              <span className="text-ac-text-muted w-[52px] shrink-0 tabular-nums font-mono">
                {new Date(event.created_at).toLocaleTimeString("en-US", {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                  hour12: false,
                })}
              </span>
              <span className="text-ac-text-muted w-[130px] shrink-0 truncate font-mono text-[11px]">
                {event.agent_id.slice(0, 8)}…
              </span>
              <span className="font-mono text-[11px] text-ac-text-primary flex-1 truncate">
                {event.tool_name}
              </span>
              <DecisionBadge decision={event.decision} />
            </div>
          ))}
          {data?.events.length === 0 && (
            <p className="text-[12px] text-ac-text-muted py-4 text-center">
              No intercepts yet
            </p>
          )}
        </div>
      )}
    </div>
  );
}
