import { EnterpriseLock } from "@/components/shared/EnterpriseLock";

export function IntelligencePage() {
  return (
    <div className="p-6">
      <h2 className="text-[18px] font-semibold tracking-[-0.02em] text-ac-text-primary mb-4">Intelligence</h2>
      <EnterpriseLock
        title="Requires Enterprise License"
        description="Threat summaries and policy suggestions require an enterprise plan."
      />
    </div>
  );
}
