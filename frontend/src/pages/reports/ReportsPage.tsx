import { EnterpriseLock } from "@/components/shared/EnterpriseLock";

export function ReportsPage() {
  return (
    <div className="p-6">
      <h2 className="text-[18px] font-semibold tracking-[-0.02em] text-ac-text-primary mb-4">Compliance Reports</h2>
      <EnterpriseLock
        title="Requires Enterprise License"
        description="Compliance reporting requires an enterprise plan."
      />
    </div>
  );
}
