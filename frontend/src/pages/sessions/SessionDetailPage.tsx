import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { getSessionEvents } from "@/api/sessions";
import type { SessionDetailResponse } from "@/api/sessions";
import { DecisionBadge } from "@/components/shared/DecisionBadge";
import { EnterpriseLock } from "@/components/shared/EnterpriseLock";
import { ChevronLeft } from "lucide-react";
import { useLicense } from "@/hooks/useLicense";

export function SessionDetailPage() {
  const { isEnterprise } = useLicense();
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<SessionDetailResponse | null>(null);

  useEffect(() => {
    if (id) getSessionEvents(id).then(setData);
  }, [id]);

  if (!isEnterprise) {
    return (
      <div className="p-6">
        <EnterpriseLock
          title="Session Detail — Enterprise"
          description="Requires Enterprise license."
        />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <Link
        to="/sessions"
        className="flex items-center gap-1 text-sm text-ac-text-muted hover:text-ac-text-primary"
      >
        <ChevronLeft size={14} /> Back to sessions
      </Link>
      <h2 className="text-[18px] font-semibold text-ac-text-primary">
        Session{" "}
        <span className="font-mono text-[15px] text-ac-text-muted">
          {id?.slice(0, 8)}…
        </span>
      </h2>

      {data && (
        <>
          {data.trigger_context && (
            <div className="bg-ac-card border border-ac-border rounded-lg px-4 py-3">
              <span className="text-[11px] font-medium text-ac-text-muted uppercase tracking-wide">
                Trigger
              </span>
              <p className="text-[13px] text-ac-text-primary mt-0.5">
                {data.trigger_context}
              </p>
            </div>
          )}
          <div className="bg-ac-card border border-ac-border rounded-lg overflow-hidden">
          {data.events.map((event) => (
            <div
              key={event.id}
              className="flex items-start gap-4 px-4 py-3 border-b border-gray-50 text-[13px]"
            >
              <div className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center text-[11px] text-ac-text-muted font-medium shrink-0 mt-0.5">
                {event.sequence_number}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="font-mono text-[12px] text-ac-text-primary">
                    {event.tool_name}
                  </span>
                  <DecisionBadge decision={event.decision} />
                </div>
                {event.decision_reason && (
                  <p className="text-[12px] text-ac-text-muted">
                    {event.decision_reason}
                  </p>
                )}
              </div>
              <span className="text-[11px] text-ac-text-muted shrink-0">
                {new Date(event.created_at).toLocaleTimeString("en-US", {
                  hour12: false,
                })}
              </span>
            </div>
          ))}
          </div>
        </>
      )}
    </div>
  );
}
