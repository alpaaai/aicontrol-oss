import { useState, useCallback, useEffect } from "react";
import { listAuditEvents, exportAuditEvents } from "@/api/auditEvents";
import type { AuditFilters as Filters, AuditEventsResponse } from "@/api/auditEvents";
import { AuditFilters as AuditFilterBar } from "./AuditFilters";
import { AuditTable } from "./AuditTable";
import { useLicense } from "@/hooks/useLicense";

type GroupBy = "none" | "workflow" | "session";

// Spec §4: sessions fold into Audit. The standalone Sessions page is gone
// (task 1.5); this page gains grouping by session and by workflow instead.
export function AuditLogPage() {
  const [data, setData] = useState<AuditEventsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<Filters>({ limit: 50, offset: 0 });
  const [groupBy, setGroupBy] = useState<GroupBy>("none");
  const { isEnterprise } = useLicense();

  const load = useCallback(async (f: Filters) => {
    setLoading(true);
    try {
      const result = await listAuditEvents(f);
      setData(result);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(filters);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFilter = (f: Filters) => {
    setFilters(f);
    load(f);
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-title-lg text-ac-ink">Audit log</h1>
          {data && <p className="text-body-sm text-ac-muted mt-0.5">{data.total.toLocaleString()} total events</p>}
        </div>
        <div className="flex items-center gap-2">
          {isEnterprise && (
            <button
              onClick={async () => {
                const blob = await exportAuditEvents(filters);
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "audit_events.csv";
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="text-body-sm text-ac-body hover:text-ac-ink border border-ac-hairline-strong rounded-md px-3 py-1.5"
            >
              Export
            </button>
          )}
          <button
            onClick={() => load(filters)}
            className="text-body-sm text-ac-body hover:text-ac-ink border border-ac-hairline-strong rounded-md px-3 py-1.5"
          >
            Refresh
          </button>
        </div>
      </div>

      <AuditFilterBar onFilter={handleFilter} groupBy={groupBy} onGroupByChange={setGroupBy} />

      <AuditTable events={data?.events ?? []} loading={loading} groupBy={groupBy} />

      {data && data.total > data.limit && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-body-sm text-ac-muted">
            Showing {(filters.offset ?? 0) + 1}–{Math.min((filters.offset ?? 0) + data.limit, data.total)} of {data.total}
          </p>
          <div className="flex gap-2">
            <button
              disabled={!filters.offset}
              onClick={() => handleFilter({ ...filters, offset: (filters.offset ?? 0) - data.limit })}
              className="border border-ac-hairline-strong rounded-md px-3 py-1.5 text-body-sm disabled:opacity-40"
            >
              Previous
            </button>
            <button
              disabled={(filters.offset ?? 0) + data.limit >= data.total}
              onClick={() => handleFilter({ ...filters, offset: (filters.offset ?? 0) + data.limit })}
              className="border border-ac-hairline-strong rounded-md px-3 py-1.5 text-body-sm disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
