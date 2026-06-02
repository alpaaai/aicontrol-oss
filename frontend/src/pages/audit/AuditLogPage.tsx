import { useState, useCallback, useEffect } from "react";
import { listAuditEvents, exportAuditEvents } from "@/api/auditEvents";
import type { AuditFilters, AuditEventsResponse } from "@/api/auditEvents";
import { AuditFilters as AuditFilterBar } from "./AuditFilters";
import { AuditTable } from "./AuditTable";
import { RefreshCw, Download } from "lucide-react";
import { useLicense } from "@/hooks/useLicense";

export function AuditLogPage() {
  const [data, setData] = useState<AuditEventsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<AuditFilters>({ limit: 50, offset: 0 });
  const { isEnterprise } = useLicense();

  const load = useCallback(async (f: AuditFilters) => {
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

  const handleFilter = (f: AuditFilters) => {
    setFilters(f);
    load(f);
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5 animate-fade-up">
        <h2 className="text-[18px] font-semibold text-ac-text-primary">
          Agent activity
        </h2>
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
              className="flex items-center gap-1.5 text-sm text-ac-text-muted hover:text-ac-text-primary border border-ac-border rounded-lg px-3 py-1.5"
            >
              <Download size={13} />
              Export
            </button>
          )}
          <button
            onClick={() => load(filters)}
            className="flex items-center gap-1.5 text-sm text-ac-text-muted hover:text-ac-text-primary border border-ac-border rounded-lg px-3 py-1.5"
          >
            <RefreshCw size={13} />
            Refresh
          </button>
        </div>
      </div>

      <AuditFilterBar onFilter={handleFilter} />

      {data && (
        <p className="text-[12px] text-ac-text-muted mb-3">
          {data.total.toLocaleString()} total events
        </p>
      )}

      <AuditTable events={data?.events ?? []} loading={loading} />

      {/* Pagination */}
      {data && data.total > data.limit && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-ac-text-muted">
            Showing {(filters.offset ?? 0) + 1}–
            {Math.min((filters.offset ?? 0) + data.limit, data.total)} of{" "}
            {data.total}
          </p>
          <div className="flex gap-2">
            <button
              disabled={!filters.offset}
              onClick={() =>
                handleFilter({
                  ...filters,
                  offset: (filters.offset ?? 0) - data.limit,
                })
              }
              className="border border-ac-border rounded-lg px-3 py-1.5 text-sm disabled:opacity-40"
            >
              Previous
            </button>
            <button
              disabled={(filters.offset ?? 0) + data.limit >= data.total}
              onClick={() =>
                handleFilter({
                  ...filters,
                  offset: (filters.offset ?? 0) + data.limit,
                })
              }
              className="border border-ac-border rounded-lg px-3 py-1.5 text-sm disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
