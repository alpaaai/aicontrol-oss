import { EnterpriseLock } from "@/components/shared/EnterpriseLock";

export function ReviewQueuePage() {
  return (
    <div className="p-6">
      <h2 className="text-[18px] font-semibold tracking-[-0.02em] text-ac-text-primary mb-4">Review Queue</h2>
      <EnterpriseLock
        title="Requires Enterprise License"
        description="Human-in-the-loop review requires an enterprise plan."
      />
    </div>
  );
}
