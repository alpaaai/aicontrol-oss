import { useState } from "react";
import type { AuditEvent } from "@/api/auditEvents";
import { DecisionBadge } from "@/components/shared/DecisionBadge";
import { useOrgSettings } from "@/context/OrgSettingsContext";
import { formatTs } from "@/lib/formatDate";

interface Props {
  events: AuditEvent[];
  loading: boolean;
}

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
  className,
}: {
  label: string;
  value: string;
  mono?: boolean;
  labelColor: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <p className={`text-[10px] uppercase tracking-wide font-medium mb-0.5 ${labelColor}`}>
        {label}
      </p>
      <p className={`text-[12px] text-ac-text-primary break-all ${mono ? "font-mono" : ""}`}>
        {value}
      </p>
    </div>
  );
}

function AuditRow({ event }: { event: AuditEvent }) {
  const [open, setOpen] = useState(false);
  const { timezone } = useOrgSettings();

  const readable = `Agent ${event.agent_name} call to ${event.tool_name} tool ${decisionVerb[event.decision]}.`;
  const timestamp = formatTs(event.created_at, timezone, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  const lc = expandedLabelColor[event.decision];

  return (
    <div className="bg-ac-card border border-ac-border rounded-lg overflow-hidden">
      {/* Main row */}
      <div
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-4 px-4 py-3 cursor-pointer hover:bg-ac-peacock-50 transition-colors"
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
          <Detail label="Reason" value={event.decision_reason ?? "No reason provided"} labelColor={lc} />

          {event.tool_parameters && (
            <div>
              <p className={`text-[10px] uppercase tracking-wide font-medium mb-0.5 ${lc}`}>
                Parameters
              </p>
              <p className="text-[12px] font-mono text-ac-text-primary bg-white/60 rounded px-2 py-1.5 break-all">
                {event.tool_parameters}
              </p>
            </div>
          )}

          {event.policy_name && (
            <div>
              <p className={`text-[10px] uppercase tracking-wide font-medium mb-1 ${lc}`}>
                Policies fired
              </p>
              <div className="flex items-center gap-3">
                <span className="text-[12px] text-ac-text-primary font-medium">
                  {event.policy_name}
                </span>
                {event.policy_id && (
                  <span className="text-[11px] font-mono text-ac-text-muted">
                    {event.policy_id}
                  </span>
                )}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <Detail label="Agent" value={event.agent_name} labelColor={lc} />
            <Detail label="Agent ID" value={event.agent_id} mono labelColor={lc} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Detail label="Session ID" value={event.session_id} mono labelColor={lc} />
            <Detail label="Event ID" value={event.id} mono labelColor={lc} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Detail label="Sequence" value={`#${event.sequence_number}`} labelColor={lc} />
            <Detail
              label="Duration"
              value={event.duration_ms != null ? `${event.duration_ms}ms` : "—"}
              labelColor={lc}
            />
          </div>

          {event.tool_response && (
            <div>
              <p className={`text-[10px] uppercase tracking-wide font-medium mb-0.5 ${lc}`}>
                Tool response
              </p>
              <p className="text-[12px] font-mono text-ac-text-primary bg-white/60 rounded px-2 py-1.5 break-all">
                {event.tool_response}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function AuditTable({ events, loading }: Props) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="h-[58px] bg-gray-50 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <p className="text-center text-sm text-ac-text-muted py-10">
        No events match the current filters.
      </p>
    );
  }

  return (
    <>
      {/* Column headers */}
      <div className="flex items-center gap-4 px-4 pb-1.5 text-[11px] font-medium text-ac-text-muted uppercase tracking-wide">
        <div className="flex-1">Activity</div>
        <span className="hidden sm:block w-[130px] shrink-0 text-right">Policy</span>
        <span className="w-[60px] shrink-0 text-right">Duration</span>
        <span className="w-[68px] shrink-0 text-right">Decision</span>
      </div>

      <div className="space-y-2">
        {events.map((event) => (
          <AuditRow key={event.id} event={event} />
        ))}
      </div>
    </>
  );
}
