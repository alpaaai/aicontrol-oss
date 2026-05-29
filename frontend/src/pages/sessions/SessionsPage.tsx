import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { listSessions } from "@/api/sessions";
import type { Session } from "@/api/sessions";
import { EnterpriseLock } from "@/components/shared/EnterpriseLock";

const IS_ENTERPRISE = import.meta.env.VITE_ENTERPRISE === "true";

function SessionsTable() {
  const [data, setData] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    listSessions().then((r) => {
      setData(r.sessions);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div className="h-10 bg-gray-50 rounded animate-pulse" />;
  }

  return (
    <div className="bg-ac-card border border-ac-border rounded-[10px] overflow-hidden">
      <div
        className="grid gap-3 px-4 py-2.5 text-[11px] font-medium text-ac-text-muted uppercase
                   tracking-wide border-b border-ac-border bg-gray-50"
        style={{ gridTemplateColumns: "1fr 200px 120px 160px" }}
      >
        <div>Session ID</div>
        <div>Agent ID</div>
        <div>Risk Score</div>
        <div>Started</div>
      </div>
      {data.map((s) => (
        <div
          key={s.id}
          onClick={() => navigate(`/sessions/${s.id}`)}
          className="grid gap-3 px-4 py-2.5 text-[13px] border-b border-gray-50
                     hover:bg-gray-50 cursor-pointer transition-colors"
          style={{ gridTemplateColumns: "1fr 200px 120px 160px" }}
        >
          <div className="font-mono text-[11px] text-ac-text-muted truncate">{s.id}</div>
          <div className="font-mono text-[11px] text-ac-text-muted truncate">
            {s.agent_id ?? "—"}
          </div>
          <div className="text-ac-text-muted">{s.risk_score ?? "—"}</div>
          <div className="text-ac-text-muted text-[12px]">
            {s.started_at
              ? new Date(s.started_at).toLocaleString("en-US", {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                  hour12: false,
                })
              : "—"}
          </div>
        </div>
      ))}
    </div>
  );
}

export function SessionsPage() {
  if (!IS_ENTERPRISE) {
    return (
      <div className="p-6">
        <h2 className="text-[18px] font-semibold text-ac-text-primary mb-4">
          Sessions
        </h2>
        <EnterpriseLock
          title="Sessions — Enterprise Feature"
          description="Session drill-down and event timeline requires an Enterprise license."
        >
          <div className="space-y-2 p-4">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="flex gap-4 text-sm text-ac-text-muted py-2 border-b border-gray-100"
              >
                <span className="font-mono">a3f9b2c1-xxxx-xxxx-xxxx-xxxx</span>
                <span>clinical-doc-agent</span>
                <span>14 events</span>
              </div>
            ))}
          </div>
        </EnterpriseLock>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <h2 className="text-[18px] font-semibold text-ac-text-primary">
        Sessions
      </h2>
      <SessionsTable />
    </div>
  );
}
