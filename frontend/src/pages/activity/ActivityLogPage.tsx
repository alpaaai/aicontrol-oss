import { useCallback, useEffect, useState } from "react";
import { listActivityLog } from "@/api/activityLog";
import type { ActivityLogFilters, ActivityLogResponse } from "@/api/activityLog";
import { EmptyState } from "@/components/primitives/EmptyState";

function formatState(state: Record<string, unknown> | null): string {
  if (!state || Object.keys(state).length === 0) return "—";
  return Object.entries(state)
    .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
    .join(", ");
}

export function ActivityLogPage() {
  const [data, setData] = useState<ActivityLogResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [filters, setFilters] = useState<ActivityLogFilters>({ limit: 50, offset: 0 });

  const load = useCallback(async (f: ActivityLogFilters) => {
    setLoading(true);
    setLoadError(false);
    try {
      const result = await listActivityLog(f);
      setData(result);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-title-lg text-ac-ink">Activity log</h1>
          {data && (
            <p className="text-body-sm text-ac-muted mt-0.5">
              {data.total.toLocaleString()} admin action{data.total === 1 ? "" : "s"}
            </p>
          )}
        </div>
        <button
          onClick={() => load(filters)}
          className="text-body-sm text-ac-body hover:text-ac-ink border border-ac-hairline-strong rounded-md px-3 py-1.5"
        >
          Refresh
        </button>
      </div>

      {loadError && (
        <p className="text-body-sm text-ac-error mb-3">Couldn't load activity log. Try Refresh.</p>
      )}

      {loading ? (
        <div className="h-40 bg-ac-surface-sunk rounded-lg animate-pulse" />
      ) : !loadError && (data?.logs.length ?? 0) === 0 ? (
        <EmptyState title="No admin activity recorded yet." />
      ) : (
        <div className="border border-ac-hairline rounded-lg overflow-hidden">
          <table className="w-full text-body-sm">
            <thead className="bg-ac-surface-sunk text-ac-muted text-left">
              <tr>
                <th className="px-3 py-2 font-medium">Time</th>
                <th className="px-3 py-2 font-medium">Actor</th>
                <th className="px-3 py-2 font-medium">Action</th>
                <th className="px-3 py-2 font-medium">Resource</th>
                <th className="px-3 py-2 font-medium">Before</th>
                <th className="px-3 py-2 font-medium">After</th>
              </tr>
            </thead>
            <tbody>
              {data?.logs.map((entry) => (
                <tr key={entry.id} className="border-t border-ac-hairline">
                  <td className="px-3 py-2 text-ac-body whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-ac-body">{entry.user_email ?? "—"}</td>
                  <td className="px-3 py-2 text-ac-ink font-medium">{entry.action}</td>
                  <td className="px-3 py-2 text-ac-body">
                    {entry.resource_type ?? "—"}
                    {entry.resource_id ? ` / ${entry.resource_id.slice(0, 8)}` : ""}
                  </td>
                  <td className="px-3 py-2 text-ac-muted max-w-xs truncate" title={formatState(entry.before_state)}>
                    {formatState(entry.before_state)}
                  </td>
                  <td className="px-3 py-2 text-ac-muted max-w-xs truncate" title={formatState(entry.after_state)}>
                    {formatState(entry.after_state)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.total > (filters.limit ?? 50) && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-body-sm text-ac-muted">
            Showing {(filters.offset ?? 0) + 1}–{Math.min((filters.offset ?? 0) + (filters.limit ?? 50), data.total)} of {data.total}
          </p>
          <div className="flex gap-2">
            <button
              disabled={!filters.offset}
              onClick={() => {
                const next = { ...filters, offset: (filters.offset ?? 0) - (filters.limit ?? 50) };
                setFilters(next);
                load(next);
              }}
              className="border border-ac-hairline-strong rounded-md px-3 py-1.5 text-body-sm disabled:opacity-40"
            >
              Previous
            </button>
            <button
              disabled={(filters.offset ?? 0) + (filters.limit ?? 50) >= data.total}
              onClick={() => {
                const next = { ...filters, offset: (filters.offset ?? 0) + (filters.limit ?? 50) };
                setFilters(next);
                load(next);
              }}
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
