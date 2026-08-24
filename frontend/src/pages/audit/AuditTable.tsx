import type { AuditEvent } from "@/api/auditEvents";
import { AuditRow } from "./AuditRow";

type GroupBy = "none" | "workflow" | "session";

function groupEvents(events: AuditEvent[], groupBy: GroupBy): [string, AuditEvent[]][] {
  if (groupBy === "none") return [["", events]];
  const key = groupBy === "workflow" ? (e: AuditEvent) => e.workflow ?? "unassigned" : (e: AuditEvent) => e.session_id;
  const groups = new Map<string, AuditEvent[]>();
  for (const event of events) {
    const k = key(event);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k)!.push(event);
  }
  return [...groups.entries()];
}

export function AuditTable(props: { events: AuditEvent[]; loading: boolean; groupBy: GroupBy }) {
  const { events, loading, groupBy } = props;

  if (loading) {
    return (
      <div className="space-y-2">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="h-[58px] bg-ac-surface-sunk rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (events.length === 0) {
    return <p className="text-center text-body-sm text-ac-muted py-10">No events match the current filters.</p>;
  }

  const groups = groupEvents(events, groupBy);

  return (
    <div data-testid="audit-table" className="max-h-[640px] overflow-y-auto space-y-6">
      {groups.map(([key, groupEvents]) => (
        <div key={key || "flat"} data-testid={key ? `${groupBy}-group-${key}` : undefined}>
          {key && <h3 className="text-title-sm text-ac-ink mb-2">{key}</h3>}
          <div className="space-y-2">
            {groupEvents.map((event) => (
              <AuditRow key={event.id} event={event} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
