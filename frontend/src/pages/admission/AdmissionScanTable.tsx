import { useState } from "react";
import type { AdmissionScan, AdmissionScanFinding } from "@/api/admissionScans";

interface Props {
  scans: AdmissionScan[];
  loading: boolean;
}

const severityStyles: Record<AdmissionScanFinding["severity"], string> = {
  critical: "bg-red-50 text-red-700 border border-red-200",
  high: "bg-orange-50 text-orange-700 border border-orange-200",
  medium: "bg-amber-50 text-amber-700 border border-amber-200",
  low: "bg-blue-50 text-blue-700 border border-blue-200",
  info: "bg-gray-50 text-gray-600 border border-gray-200",
};

const statusStyles: Record<AdmissionScan["status"], string> = {
  completed: "text-ac-allow",
  failed: "text-ac-deny",
  running: "text-ac-review",
  pending: "text-ac-text-muted",
};

function SeverityBadge({ severity }: { severity: AdmissionScanFinding["severity"] }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium ${severityStyles[severity]}`}
    >
      {severity.charAt(0).toUpperCase() + severity.slice(1)}
    </span>
  );
}

function highestSeverity(scan: AdmissionScan): AdmissionScanFinding["severity"] | null {
  const order: AdmissionScanFinding["severity"][] = ["critical", "high", "medium", "low", "info"];
  for (const level of order) {
    if (scan.severity_summary[level]) return level;
  }
  return null;
}

function AdmissionScanRow({ scan }: { scan: AdmissionScan }) {
  const [open, setOpen] = useState(false);
  const topSeverity = highestSeverity(scan);
  const timestamp = scan.created_at
    ? new Date(scan.created_at).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "—";

  return (
    <div className="bg-ac-card border border-ac-border rounded-[10px] overflow-hidden">
      <div
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-4 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-medium text-ac-text-primary truncate">
            {scan.scanner_name} scanned {scan.target_ref}
          </p>
          <p className="text-[11px] text-ac-text-muted mt-0.5">{timestamp}</p>
        </div>

        <span className="text-[12px] text-ac-text-muted hidden sm:block w-[90px] shrink-0 text-right">
          {scan.findings.length} finding{scan.findings.length === 1 ? "" : "s"}
        </span>

        <span className={`text-[12px] font-medium w-[70px] shrink-0 text-right ${statusStyles[scan.status]}`}>
          {scan.status.charAt(0).toUpperCase() + scan.status.slice(1)}
        </span>

        <div className="shrink-0 w-[80px] text-right">
          {topSeverity && <SeverityBadge severity={topSeverity} />}
        </div>
      </div>

      {open && (
        <div className="border-t border-ac-border px-4 py-3 space-y-2 bg-gray-50">
          {scan.findings.length === 0 ? (
            <p className="text-[12px] text-ac-text-muted">No findings.</p>
          ) : (
            scan.findings.map((f, i) => (
              <div key={i} className="flex items-start gap-3 bg-white rounded-lg px-3 py-2 border border-ac-border">
                <SeverityBadge severity={f.severity} />
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-medium text-ac-text-primary">{f.message}</p>
                  <p className="text-[11px] text-ac-text-muted mt-0.5 font-mono">
                    {f.rule_id}
                    {f.location ? ` · ${f.location}` : ""}
                  </p>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export function AdmissionScanTable({ scans, loading }: Props) {
  if (loading && scans.length === 0) {
    return (
      <div className="space-y-2">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-[58px] bg-gray-50 rounded-[10px] animate-pulse" />
        ))}
      </div>
    );
  }

  if (scans.length === 0) {
    return (
      <p className="text-center text-sm text-ac-text-muted py-10">
        No admission scans yet.
      </p>
    );
  }

  return (
    <>
      <div className="flex items-center gap-4 px-4 pb-1.5 text-[11px] font-medium text-ac-text-muted uppercase tracking-wide">
        <div className="flex-1">Scan</div>
        <span className="hidden sm:block w-[90px] shrink-0 text-right">Findings</span>
        <span className="w-[70px] shrink-0 text-right">Status</span>
        <span className="w-[80px] shrink-0 text-right">Severity</span>
      </div>

      <div className="space-y-2">
        {scans.map((scan) => (
          <AdmissionScanRow key={scan.id} scan={scan} />
        ))}
      </div>
    </>
  );
}
