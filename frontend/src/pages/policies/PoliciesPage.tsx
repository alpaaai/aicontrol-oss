import { useState, useEffect } from "react";
import { listPolicies, listLibraryPolicies, deletePolicy } from "@/api/policies";
import type { Policy } from "@/api/policies";
import { PolicyTable } from "./PolicyTable";
import { PolicyEditor } from "./PolicyEditor";
import { PolicyLibrary } from "./PolicyLibrary";
import { DriftWarnings } from "./DriftWarnings";
import { Plus } from "lucide-react";

type Tab = "active" | "library";

export function PoliciesPage() {
  const [tab, setTab] = useState<Tab>("active");
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [libraryPolicies, setLibraryPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Policy | null>(null);

  const loadActive = () => {
    setLoading(true);
    listPolicies()
      .then(setPolicies)
      .finally(() => setLoading(false));
  };

  const loadLibrary = () => {
    setLibraryLoading(true);
    listLibraryPolicies()
      .then(setLibraryPolicies)
      .finally(() => setLibraryLoading(false));
  };

  useEffect(() => {
    loadActive();
  }, []);

  useEffect(() => {
    if (tab === "library" && libraryPolicies.length === 0) {
      loadLibrary();
    }
  }, [tab]);

  const handleDelete = async (p: Policy) => {
    if (!confirm(`Delete policy "${p.name}"? This cannot be undone.`)) return;
    await deletePolicy(p.id);
    loadActive();
  };

  const handleActivateLibrary = (policy: Policy) => {
    setEditTarget({
      ...policy,
      id: "",
      active: true,
      library: false,
    } as Policy);
    setDialogOpen(true);
  };

  return (
    <div className="p-6">
      {/* Page header */}
      <div className="flex items-center justify-between mb-5 animate-fade-up">
        <div>
          <h2 className="text-[18px] font-semibold text-ac-text-primary">Policies</h2>
          <p className="text-sm text-ac-text-muted mt-0.5">
            {tab === "active"
              ? loading ? "—" : `${policies.length} active polic${policies.length !== 1 ? "ies" : "y"}`
              : `${libraryPolicies.length} templates available`}
          </p>
        </div>

        {tab === "active" && (
          <button
            onClick={() => {
              setEditTarget(null);
              setDialogOpen(true);
            }}
            className="flex items-center gap-1.5 bg-ac-primary text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-ac-primary/90"
          >
            <Plus size={14} /> New policy
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-0 mb-5 border-b border-ac-border">
        {(["active", "library"] as Tab[]).map((t) => (
          <button
            key={t}
            role="tab"
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-[13px] font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? "border-ac-primary text-ac-primary"
                : "border-transparent text-ac-text-muted hover:text-ac-text-primary"
            }`}
          >
            {t === "active" ? "Active Policies" : "Policy Library"}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "active" ? (
        <>
          {loading ? (
            <div className="h-40 bg-gray-50 rounded animate-pulse" />
          ) : (
            <PolicyTable
              policies={policies}
              onEdit={(p) => {
                setEditTarget(p);
                setDialogOpen(true);
              }}
              onDelete={handleDelete}
            />
          )}
          <DriftWarnings />
        </>
      ) : (
        <PolicyLibrary
          policies={libraryPolicies}
          loading={libraryLoading}
          onActivate={handleActivateLibrary}
        />
      )}

      <PolicyEditor
        open={dialogOpen}
        policy={editTarget}
        onClose={() => setDialogOpen(false)}
        onSaved={() => {
          setDialogOpen(false);
          loadActive();
        }}
      />
    </div>
  );
}
