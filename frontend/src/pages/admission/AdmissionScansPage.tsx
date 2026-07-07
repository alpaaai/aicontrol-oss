import { useCallback } from "react";
import { RefreshCw } from "lucide-react";
import { listAdmissionScans } from "@/api/admissionScans";
import { usePoll } from "@/hooks/usePoll";
import { AdmissionScanTable } from "./AdmissionScanTable";

export function AdmissionScansPage() {
  const fetcher = useCallback(() => listAdmissionScans(), []);
  const { data, loading, refetch } = usePoll(fetcher, 5000);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5 animate-fade-up">
        <h2 className="text-[18px] font-semibold text-ac-text-primary">
          Admission scans
        </h2>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 text-sm text-ac-text-muted hover:text-ac-text-primary border border-ac-border rounded-lg px-3 py-1.5"
        >
          <RefreshCw size={13} />
          Refresh
        </button>
      </div>

      {data && (
        <p className="text-[12px] text-ac-text-muted mb-3">
          {data.length.toLocaleString()} scan{data.length === 1 ? "" : "s"}
        </p>
      )}

      <AdmissionScanTable scans={data ?? []} loading={loading} />
    </div>
  );
}
