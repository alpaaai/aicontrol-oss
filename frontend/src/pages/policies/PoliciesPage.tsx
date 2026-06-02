import { useState, useEffect } from "react";
import { listPolicies, deletePolicy } from "@/api/policies";
import type { Policy } from "@/api/policies";
import { PolicyTable } from "./PolicyTable";
import { PolicyFormDialog } from "./PolicyFormDialog";
import { DriftWarnings } from "./DriftWarnings";
import { Plus } from "lucide-react";

export function PoliciesPage() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Policy | null>(null);
  const [frameworkFilter, setFrameworkFilter] = useState("");

  const load = () => {
    setLoading(true);
    listPolicies()
      .then((data) => setPolicies(data))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const handleDelete = async (p: Policy) => {
    if (!confirm(`Delete policy "${p.name}"? This cannot be undone.`)) return;
    await deletePolicy(p.id);
    load();
  };

  const allFrameworks = Array.from(
    new Set(policies.flatMap((p) => p.compliance_frameworks ?? []))
  ).sort();

  const visiblePolicies = frameworkFilter
    ? policies.filter((p) => p.compliance_frameworks?.includes(frameworkFilter))
    : policies;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5 animate-fade-up">
        <div>
          <h2 className="text-[18px] font-semibold text-ac-text-primary">
            Policies
          </h2>
          <p className="text-sm text-ac-text-muted mt-0.5">
            {loading ? "—" : `${visiblePolicies.length} policies`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {allFrameworks.length > 0 && (
            <select
              value={frameworkFilter}
              onChange={(e) => setFrameworkFilter(e.target.value)}
              className="border border-ac-border rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 bg-white"
            >
              <option value="">All frameworks</option>
              {allFrameworks.map((fw) => (
                <option key={fw} value={fw}>{fw}</option>
              ))}
            </select>
          )}
          <button
            onClick={() => {
              setEditTarget(null);
              setDialogOpen(true);
            }}
            className="flex items-center gap-1.5 bg-ac-primary text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-ac-primary/90"
          >
            <Plus size={14} /> New policy
          </button>
        </div>
      </div>

      {loading ? (
        <div className="h-40 bg-gray-50 rounded animate-pulse" />
      ) : (
        <PolicyTable
          policies={visiblePolicies}
          onEdit={(p) => {
            setEditTarget(p);
            setDialogOpen(true);
          }}
          onDelete={handleDelete}
        />
      )}

      <DriftWarnings />

      <PolicyFormDialog
        open={dialogOpen}
        policy={editTarget}
        onClose={() => setDialogOpen(false)}
        onSaved={() => {
          setDialogOpen(false);
          load();
        }}
      />
    </div>
  );
}
