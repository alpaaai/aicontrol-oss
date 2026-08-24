import { useState } from "react";
import type { AuditEvent } from "@/api/auditEvents";
import { PolicySentence } from "@/components/primitives/PolicySentence";
import { DecisionPill } from "@/components/primitives/DecisionPill";
import { useOrgSettings } from "@/context/OrgSettingsContext";
import { formatTs } from "@/lib/formatDate";

export function AuditRow(props: { event: AuditEvent }) {
  const { event } = props;
  const [open, setOpen] = useState(false);
  const { timezone } = useOrgSettings();

  const timestamp = formatTs(event.created_at, timezone, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  });

  return (
    <div data-testid={`audit-row-${event.id}`} className="border border-ac-hairline rounded-lg bg-ac-surface-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-4 px-4 py-3 text-left hover:bg-ac-surface-sunk transition-colors duration-standard focus:outline focus:outline-2 focus:outline-ac-primary focus:outline-offset-[-2px]"
      >
        <div className="flex-1 min-w-0">
          {event.policy ? (
            <PolicySentence policy={event.policy} variant="inline" />
          ) : (
            <p className="text-sentence-inline text-ac-ink truncate">
              {event.agent_name} called {event.tool_name}
            </p>
          )}
          <p className="text-caption text-ac-muted mt-0.5">{timestamp}</p>
        </div>
        <DecisionPill decision={event.decision} />
      </button>

      {open && (
        <div className="border-t border-ac-hairline px-4 py-3 space-y-3 bg-ac-canvas-soft">
          <p className="text-body-sm text-ac-body">{event.decision_reason ?? "No reason provided"}</p>
          <div className="grid grid-cols-2 gap-3 text-body-sm">
            <div>
              <p className="text-caption text-ac-muted">Agent</p>
              <p className="text-identifier text-ac-body-strong">{event.agent_name}</p>
            </div>
            <div>
              <p className="text-caption text-ac-muted">Session</p>
              <p className="text-identifier text-ac-body-strong break-all">{event.session_id}</p>
            </div>
            <div>
              <p className="text-caption text-ac-muted">Sequence</p>
              <p className="text-identifier text-ac-body-strong">#{event.sequence_number}</p>
            </div>
            <div>
              <p className="text-caption text-ac-muted">Duration</p>
              <p className="text-identifier text-ac-body-strong">{event.duration_ms != null ? `${event.duration_ms}ms` : "—"}</p>
            </div>
          </div>
          {event.tool_parameters && (
            <div>
              <p className="text-caption text-ac-muted mb-1">Parameters</p>
              <p className="text-code text-ac-body-strong bg-ac-surface-sunk rounded-md px-2 py-1.5 break-all">{event.tool_parameters}</p>
            </div>
          )}
          {event.tool_response && (
            <div>
              <p className="text-caption text-ac-muted mb-1">Tool response</p>
              <p className="text-code text-ac-body-strong bg-ac-surface-sunk rounded-md px-2 py-1.5 break-all">{event.tool_response}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
