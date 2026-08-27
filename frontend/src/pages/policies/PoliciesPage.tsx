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
  const [tab, setTab] = useState<"active" | "library">("active");

  const reload = () => listPolicies().then(setPolicies).catch(() => setPolicies([]));

  useEffect(() => {
    reload();
    getLicenseFeatures()
      .then((r) => setFeatures(r.features))
      .catch(() => {});
  }, []);

  // GET /policies returns every row -- active, library templates, and plain
  // inactive reference policies alike. Active is the only tab that means what
  // its count says; everything not active (library=true templates and the
  // example_* reference rows) is a candidate to activate, so it shares one tab.
  const activePolicies = policies?.filter((p) => p.active === true) ?? null;
  const libraryPolicies = policies?.filter((p) => p.active !== true) ?? null;
  const visible = tab === "active" ? activePolicies : libraryPolicies;

  return (
    <div className="p-6 space-y-8">
      <div>
        <h1 className="text-title-lg text-ac-ink">Policies</h1>
        <p className="text-body-sm text-ac-muted mt-0.5">
          {activePolicies === null
            ? "—"
            : `${activePolicies.length} active polic${activePolicies.length === 1 ? "y" : "ies"}`}
        </p>
      </div>

      <div className={features?.nl_authoring ? "grid grid-cols-1 md:grid-cols-2 gap-6" : ""}>
        {features?.nl_authoring && <NLComposer onCreated={reload} />}
        <StructuredEditor onCreated={reload} />
      </div>

      <div>
        <div role="tablist" className="flex gap-6 border-b border-ac-hairline mb-3">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "active"}
            onClick={() => setTab("active")}
            className={`text-title-md pb-2 -mb-px border-b-2 transition-colors duration-standard ${
              tab === "active" ? "text-ac-ink border-ac-primary" : "text-ac-muted border-transparent hover:text-ac-body"
            }`}
          >
            Active
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "library"}
            onClick={() => setTab("library")}
            className={`text-title-md pb-2 -mb-px border-b-2 transition-colors duration-standard ${
              tab === "library" ? "text-ac-ink border-ac-primary" : "text-ac-muted border-transparent hover:text-ac-body"
            }`}
          >
            Library
          </button>
        </div>
        {visible === null ? (
          <div className="h-40 bg-ac-surface-sunk rounded-lg animate-pulse" />
        ) : visible.length === 0 ? (
          <EmptyState
            title={
              tab === "active"
                ? "No policies yet — describe one in plain English."
                : "No library policies available."
            }
          />
        ) : (
          <ul data-testid="policy-list" className="space-y-3 max-h-[560px] overflow-y-auto">
            {visible.map((p) => (
              <PolicyRow key={p.id} policy={p} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
