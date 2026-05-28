import { EnterpriseLock } from "@/components/shared/EnterpriseLock";

export function SessionsPage() {
  return (
    <div className="p-6">
      <h2 className="text-[18px] font-semibold tracking-[-0.02em] text-ac-text-primary mb-4">Sessions</h2>
      <EnterpriseLock
        title="Requires Enterprise License"
        description="Session replay and inspection require an enterprise plan."
      />
    </div>
  );
}
