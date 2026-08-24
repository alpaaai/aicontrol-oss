import { useCallback } from "react";
import { usePoll } from "@/hooks/usePoll";
import { listAuditEvents } from "@/api/auditEvents";
import type { AuditEvent } from "@/api/auditEvents";
import { DecisionPill } from "@/components/primitives/DecisionPill";

function FeedRow({ event }: { event: AuditEvent }) {
  const timestamp = new Date(event.created_at).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b border-ac-hairline-soft">
      <div className="flex-1 min-w-0">
        <p className="text-body-sm text-ac-body-strong truncate">
          {event.agent_name} called {event.tool_name}
        </p>
        <p className="text-caption text-ac-muted mt-0.5">{timestamp}</p>
      </div>
      {event.policy_name && (
        <span className="text-identifier text-ac-muted hidden sm:block truncate max-w-[180px]">
          {event.policy_name}
        </span>
      )}
      <DecisionPill decision={event.decision} />
    </div>
  );
}

export function DecisionFeed() {
  const fetcher = useCallback(() => listAuditEvents({ limit: 20 }), []);
  const { data } = usePoll(fetcher, 4000);

  return (
    <div data-testid="decision-feed" className="max-h-[480px] overflow-y-auto border border-ac-hairline rounded-lg bg-ac-surface-card">
      {data?.events.length ? (
        data.events.map((event) => <FeedRow key={event.id} event={event} />)
      ) : (
        <p className="text-body-sm text-ac-muted py-6 text-center">No governed calls yet</p>
      )}
    </div>
  );
}
