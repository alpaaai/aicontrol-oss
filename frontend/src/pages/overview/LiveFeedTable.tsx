import { useState, useCallback } from "react";
import { usePoll } from "@/hooks/usePoll";
import { listAuditEvents } from "@/api/auditEvents";
import type { AuditEvent } from "@/api/auditEvents";
import { DecisionBadge } from "@/components/shared/DecisionBadge";

const decisionVerb: Record<AuditEvent["decision"], string> = {
  allow: "was approved",
  deny: "was denied",
  review: "was sent for review",
};

const expandedBg: Record<AuditEvent["decision"], string> = {
  allow: "bg-green-50 border-green-100",
  deny: "bg-red-50 border-red-100",
  review: "bg-amber-50 border-amber-100",
};

const expandedLabelColor: Record<AuditEvent["decision"], string> = {
  allow: "text-green-700",
  deny: "text-red-700",
  review: "text-amber-700",
};

function Detail({
  label,
  value,
  mono,
  labelColor,
}: {
  label: string;
  value: string;
  mono?: boolean;
  labelColor: string;
}) {
  return (
    <div>
      <p className={`text-[10px] uppercase tracking-wide font-medium mb-0.5 ${labelColor}`}>
        {label}
      </p>
      <p className={`text-[12px] text-ac-text-primary truncate ${mono ? "font-mono" : ""}`}>
        {value}
      </p>
    </div>
  );
}

function LiveFeedRow({ event, index }: { event: AuditEvent; index: number }) {
  const [open, setOpen] = useState(false);

  const readable = `Agent ${event.agent_name} call to ${event.tool_name} tool ${decisionVerb[event.decision]}.`;
  const timestamp = new Date(event.created_at).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  return (
    <div
      className="bg-ac-card border border-ac-border rounded-[10px] overflow-hidden animate-row-in"
      style={{ animationDelay: `${index * 30}ms` }}
    >
      {/* Main row */}
      <div
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-4 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-medium text-ac-text-primary truncate">{readable}</p>
          <p className="text-[11px] text-ac-text-muted mt-0.5">{timestamp}</p>
        </div>

        <span className="text-[12px] text-ac-text-muted hidden sm:block w-[130px] shrink-0 truncate text-right">
          {event.policy_name ?? "—"}
        </span>

        <span className="text-[12px] text-ac-text-muted w-[60px] shrink-0 text-right tabular-nums">
          {event.duration_ms != null ? `${event.duration_ms}ms` : "—"}
        </span>

        <div className="shrink-0">
          <DecisionBadge decision={event.decision} />
        </div>
      </div>

      {/* Accordion detail */}
      {open && (
        <div className={`border-t px-4 py-3 space-y-3 ${expandedBg[event.decision]}`}>
          <div className="grid grid-cols-2 gap-3">
            <Detail label="Agent" value={event.agent_name} labelColor={expandedLabelColor[event.decision]} />
            <Detail label="Tool" value={event.tool_name} labelColor={expandedLabelColor[event.decision]} />
          </div>

          {event.policy_name && (
            <div>
              <p className={`text-[10px] uppercase tracking-wide font-medium mb-1 ${expandedLabelColor[event.decision]}`}>
                Policies fired
              </p>
              <div className="flex items-center gap-3">
                <span className="text-[12px] text-ac-text-primary font-medium">{event.policy_name}</span>
                {event.policy_id && (
                  <span className="text-[11px] font-mono text-ac-text-muted">{event.policy_id}</span>
                )}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <Detail label="Session ID" value={event.session_id} mono labelColor={expandedLabelColor[event.decision]} />
            <Detail label="Event ID" value={event.id} mono labelColor={expandedLabelColor[event.decision]} />
          </div>
        </div>
      )}
    </div>
  );
}

export function LiveFeedTable() {
  const fetcher = useCallback(() => listAuditEvents({ limit: 20 }), []);
  const { data, loading } = usePoll(fetcher, 4000);

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-ac-allow opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-ac-allow" />
        </span>
        <p className="text-[12px] font-medium text-ac-text-muted">Live intercepts</p>

        <div className="ml-auto flex items-center gap-4 pr-1">
          <span className="text-[11px] text-ac-text-muted hidden sm:block">Policy</span>
          <span className="text-[11px] text-ac-text-muted w-[60px] text-right">Duration</span>
          <span className="text-[11px] text-ac-text-muted w-[68px] text-right">Decision</span>
        </div>
      </div>

      {loading && !data ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-[58px] bg-gray-50 rounded-[10px] animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {data?.events.map((event: AuditEvent, i: number) => (
            <LiveFeedRow key={event.id} event={event} index={i} />
          ))}
          {data?.events.length === 0 && (
            <p className="text-[12px] text-ac-text-muted py-6 text-center">No intercepts yet</p>
          )}
        </div>
      )}
    </div>
  );
}
