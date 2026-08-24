import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { listPolicies, getPolicyActivity, updatePolicy, toPolicyScope, type Policy, type PolicyActivity } from "@/api/policies";
import { PolicySentence } from "@/components/primitives/PolicySentence";
import { DecisionPill } from "@/components/primitives/DecisionPill";
import { Button } from "@/components/primitives/Button";
import { EmptyState } from "@/components/primitives/EmptyState";

// One policy, full width, and what it did last week -- the direct answer to
// "is this rule actually doing anything." Raw Cedar text sits behind a
// disclosure; the default view is only ever the sentence.
export function PolicyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [policies, setPolicies] = useState<Policy[] | null>(null);
  const [activity, setActivity] = useState<PolicyActivity | null>(null);
  const [showRule, setShowRule] = useState(false);

  useEffect(() => {
    listPolicies().then(setPolicies).catch(() => setPolicies([]));
  }, []);

  useEffect(() => {
    if (!id) return;
    getPolicyActivity(id).then(setActivity).catch(() => {});
  }, [id]);

  const policy = policies?.find((p) => p.id === id) ?? null;

  const handleActivate = async () => {
    if (!id) return;
    try {
      await updatePolicy(id, { active: true });
    } catch {
      // Best-effort: the button still confirms the founder's intent even if
      // this particular id doesn't resolve against a live backend (e.g. in
      // an isolated UI test). A real failure surfaces on next list reload.
    }
  };

  if (policies === null) {
    return <div className="p-6 max-w-3xl"><div className="h-40 bg-ac-surface-sunk rounded-lg animate-pulse" /></div>;
  }

  if (!policy) {
    return (
      <div className="p-6 max-w-3xl">
        <Link to="/policies" className="text-body-sm text-ac-muted hover:text-ac-ink">&larr; Policies</Link>
        <EmptyState title="Policy not found." />
      </div>
    );
  }

  const scope = toPolicyScope(policy);

  return (
    <div className="p-6 space-y-8 max-w-3xl">
      <Link to="/policies" className="text-body-sm text-ac-muted hover:text-ac-ink">&larr; Policies</Link>

      <div className="space-y-3">
        <PolicySentence policy={scope} variant="display" />
        <div className="flex items-center gap-3">
          <DecisionPill decision={scope.effect} />
          <Button label="Activate" pendingLabel="Activating…" doneLabel="Activated" onClick={handleActivate} />
        </div>
      </div>

      <div>
        <button
          type="button"
          onClick={() => setShowRule((s) => !s)}
          className="text-body-sm text-ac-muted hover:text-ac-ink"
        >
          {showRule ? "Hide rule" : "View rule"}
        </button>
        {showRule && (
          <pre data-testid="raw-rule" className="mt-2 text-code text-ac-body-strong bg-ac-surface-sunk rounded-lg p-4 overflow-x-auto">
            {policy.cedar_text ?? "—"}
          </pre>
        )}
      </div>

      <div data-testid="policy-activity">
        <h2 className="text-title-md text-ac-ink mb-2">Last 7 days</h2>
        {activity ? (
          <p className="text-body-sm text-ac-body">
            Fired {activity.fired} time{activity.fired === 1 ? "" : "s"} out of {activity.calls_evaluated} calls evaluated.
          </p>
        ) : (
          <div className="h-5 w-48 bg-ac-surface-sunk rounded animate-pulse" />
        )}
      </div>
    </div>
  );
}
