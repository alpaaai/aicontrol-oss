import { useEffect, useState } from "react";
import { listPolicies, type Policy } from "@/api/policies";
import { getLicenseFeatures, type FeatureFlags } from "@/api/license";
import { NLComposer } from "./NLComposer";
import { StructuredEditor } from "./StructuredEditor";
import { PolicyRow } from "./PolicyRow";
import { EmptyState } from "@/components/primitives/EmptyState";

export function PoliciesPage() {
  const [policies, setPolicies] = useState<Policy[] | null>(null);
  const [features, setFeatures] = useState<FeatureFlags | null>(null);

  const reload = () => listPolicies().then(setPolicies).catch(() => setPolicies([]));

  useEffect(() => {
    reload();
    getLicenseFeatures()
      .then((r) => setFeatures(r.features))
      .catch(() => {});
  }, []);

  return (
    <div className="p-6 space-y-8">
      <div>
        <h1 className="text-title-lg text-ac-ink">Policies</h1>
        <p className="text-body-sm text-ac-muted mt-0.5">
          {policies === null ? "—" : `${policies.length} active polic${policies.length === 1 ? "y" : "ies"}`}
        </p>
      </div>

      <div className={features?.nl_authoring ? "grid grid-cols-1 md:grid-cols-2 gap-6" : ""}>
        {features?.nl_authoring && <NLComposer onCreated={reload} />}
        <StructuredEditor onCreated={reload} />
      </div>

      <div>
        <h2 className="text-title-md text-ac-ink mb-3">Active policies</h2>
        {policies === null ? (
          <div className="h-40 bg-ac-surface-sunk rounded-lg animate-pulse" />
        ) : policies.length === 0 ? (
          <EmptyState title="No policies yet — describe one in plain English." />
        ) : (
          <ul data-testid="policy-list" className="space-y-3 max-h-[560px] overflow-y-auto">
            {policies.map((p) => (
              <PolicyRow key={p.id} policy={p} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
