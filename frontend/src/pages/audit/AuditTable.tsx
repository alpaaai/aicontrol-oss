import { useState } from "react";
import type { AuditEvent } from "@/api/auditEvents";
import { DecisionBadge } from "@/components/shared/DecisionBadge";
import { ChevronDown, ChevronRight } from "lucide-react";

interface Props {
  events: AuditEvent[];
  loading: boolean;
}

export function AuditTable({ events, loading }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="space-y-2">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="h-10 bg-gray-50 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="bg-ac-card border border-ac-border rounded-[10px] overflow-hidden">
      {/* Header */}
      <div
        className="grid gap-3 px-4 py-2.5 text-[11px] font-medium text-ac-text-muted uppercase tracking-wide
                   border-b border-ac-border bg-gray-50"
        style={{ gridTemplateColumns: "28px 140px 1fr 140px 100px 80px" }}
      >
        <div />
        <div>Time</div>
        <div>Tool</div>
        <div>Policy</div>
        <div>Duration</div>
        <div>Decision</div>
      </div>

      {events.length === 0 && (
        <div className="text-center text-sm text-ac-text-muted py-10">
          No events match the current filters.
        </div>
      )}

      {events.map((event) => (
        <div key={event.id}>
          <div
            onClick={() =>
              setExpanded(expanded === event.id ? null : event.id)
            }
            className="grid gap-3 px-4 py-2.5 text-[13px] border-b border-gray-50
                       hover:bg-gray-50 cursor-pointer transition-colors"
            style={{ gridTemplateColumns: "28px 140px 1fr 140px 100px 80px" }}
          >
            <div className="flex items-center text-gray-300">
              {expanded === event.id ? (
                <ChevronDown size={13} />
              ) : (
                <ChevronRight size={13} />
              )}
            </div>
            <div className="text-ac-text-muted font-mono text-[11px] flex items-center">
              {new Date(event.created_at).toLocaleString("en-US", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
                hour12: false,
              })}
            </div>
            <div className="font-mono text-[12px] text-ac-text-primary flex items-center truncate">
              {event.tool_name}
            </div>
            <div className="text-ac-text-muted text-[12px] flex items-center truncate">
              {event.policy_name ?? "—"}
            </div>
            <div className="text-ac-text-muted text-[12px] flex items-center">
              {event.duration_ms != null ? `${event.duration_ms}ms` : "—"}
            </div>
            <div className="flex items-center">
              <DecisionBadge decision={event.decision} />
            </div>
          </div>

          {/* Expanded detail */}
          {expanded === event.id && (
            <div className="px-12 py-3 bg-gray-50/80 border-b border-gray-100 space-y-2">
              <div>
                <p className="text-[10px] uppercase tracking-wide text-ac-text-muted mb-0.5">
                  Reason
                </p>
                <p className="text-[13px] text-ac-text-primary">
                  {event.decision_reason ?? "No reason provided"}
                </p>
              </div>
              {event.tool_parameters && (
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-ac-text-muted mb-0.5">
                    Parameters
                  </p>
                  <p className="text-[12px] font-mono text-ac-text-muted bg-gray-100 rounded px-2 py-1.5 truncate">
                    {event.tool_parameters}
                  </p>
                </div>
              )}
              <div className="flex gap-6">
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-ac-text-muted mb-0.5">
                    Session ID
                  </p>
                  <p className="text-[12px] font-mono text-ac-text-muted">
                    {event.session_id}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-ac-text-muted mb-0.5">
                    Event ID
                  </p>
                  <p className="text-[12px] font-mono text-ac-text-muted">
                    {event.id}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
