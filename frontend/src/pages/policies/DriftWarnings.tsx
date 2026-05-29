import { useState, useEffect } from "react";
import { listWarnings, resolveWarning } from "@/api/warnings";
import type { PolicyWarning } from "@/api/warnings";
import { EnterpriseLock } from "@/components/shared/EnterpriseLock";
import { AlertTriangle, CheckCircle } from "lucide-react";
import { useLicense } from "@/hooks/useLicense";

export function DriftWarnings() {
  const { isEnterprise } = useLicense();
  const [warnings, setWarnings] = useState<PolicyWarning[]>([]);
  const [loading, setLoading] = useState(true);
  const [notLicensed, setNotLicensed] = useState(false);
  const [resolving, setResolving] = useState<string | null>(null);

  const load = () => {
    listWarnings(true)
      .then((data) => {
        setWarnings(data);
        setNotLicensed(false);
      })
      .catch((e: unknown) => {
        const status = (e as { response?: { status?: number } })?.response?.status;
        if (status === 402 || status === 403) {
          setNotLicensed(true);
        } else {
          setWarnings([]);
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (isEnterprise) load();
    else setLoading(false);
  }, [isEnterprise]);

  const handleResolve = async (id: string) => {
    setResolving(id);
    await resolveWarning(id);
    load();
    setResolving(null);
  };

  if (!isEnterprise || notLicensed) {
    return (
      <div className="mt-6">
        <h3 className="text-[14px] font-semibold text-ac-text-primary mb-3">
          Policy Drift Warnings
        </h3>
        <EnterpriseLock
          title="Drift Detection — Enterprise"
          description="Policy drift warnings require an Enterprise license."
        >
          <div className="p-4 space-y-2">
            <div className="flex items-center gap-2 text-sm text-ac-review">
              <AlertTriangle size={13} /> Tool 'deploy_infra' ungoverned on 2
              agents
            </div>
            <div className="flex items-center gap-2 text-sm text-ac-review">
              <AlertTriangle size={13} /> Policy 'pii_access' not enforced on
              lending-agent
            </div>
          </div>
        </EnterpriseLock>
      </div>
    );
  }

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[14px] font-semibold text-ac-text-primary">
          Policy Drift Warnings
          {warnings.length > 0 && (
            <span className="ml-2 text-[11px] bg-ac-review-bg text-ac-review px-2 py-0.5 rounded-full font-medium">
              {warnings.length} active
            </span>
          )}
        </h3>
      </div>

      {loading && (
        <div className="h-10 bg-gray-50 rounded animate-pulse" />
      )}

      {!loading && warnings.length === 0 && (
        <div className="flex items-center gap-2 text-sm text-ac-allow">
          <CheckCircle size={14} /> No active drift warnings
        </div>
      )}

      <div className="space-y-2">
        {warnings.map((w) => (
          <div
            key={w.id}
            className="flex items-start gap-3 p-3 bg-ac-review-bg border border-amber-200 rounded-lg text-[13px]"
          >
            <AlertTriangle
              size={14}
              className="text-ac-review mt-0.5 shrink-0"
            />
            <div className="flex-1">
              <p className="text-ac-text-primary">{w.message}</p>
              <p className="text-[11px] text-ac-text-muted mt-0.5">
                {w.agent_name && `Agent: ${w.agent_name}`}
                {w.tool_name && ` · Tool: ${w.tool_name}`}
              </p>
            </div>
            <button
              onClick={() => handleResolve(w.id)}
              disabled={resolving === w.id}
              className="text-[12px] text-ac-text-muted hover:text-ac-text-primary border border-ac-border rounded px-2 py-1 bg-ac-card disabled:opacity-50"
            >
              {resolving === w.id ? "Resolving…" : "Resolve"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
