import { useState } from "react";
import { Card } from "@/components/primitives/Card";
import { Button } from "@/components/primitives/Button";
import {
  createPolicy,
  draftPolicy,
  simulatePolicy,
  type NLDraftResponse,
  type SimulationResult as SimulationResultData,
} from "@/api/policies";
import { DraftReview } from "./DraftReview";
import { SimulationResult } from "./SimulationResult";

// The primary input on Policies (spec §5 point 1), and the describe -> draft
// -> simulate -> activate loop (spec §6.1) end to end. Nothing reaches the
// policies table before a human clicks Activate -- draft and simulate are
// both read-only round trips.
export function NLComposer(props: { onCreated?: () => void }) {
  const [value, setValue] = useState("");
  const [draft, setDraft] = useState<NLDraftResponse | null>(null);
  const [simulation, setSimulation] = useState<SimulationResultData | null>(null);

  const handleDraft = async () => {
    if (!value.trim()) return;
    setSimulation(null);
    const result = await draftPolicy(value.trim());
    setDraft(result);
  };

  const handleSimulate = async () => {
    if (!draft?.draft) return;
    const result = await simulatePolicy(draft.draft);
    setSimulation(result);
  };

  const handleActivate = async () => {
    if (!draft?.draft) return;
    await createPolicy({
      name: value.trim().slice(0, 100),
      condition: draft.draft.condition,
      principal_type: draft.draft.principal_type,
      principal_id: draft.draft.principal_id,
      action_tool: draft.draft.action_tool,
      resource_system: draft.draft.resource_system,
      effect: draft.draft.effect,
    });
    // The draft stays on screen showing "Activated" -- the Button primitive's
    // own done state -- rather than resetting immediately, which would
    // unmount it before that state ever painted. A new description starts
    // the next draft cycle.
    props.onCreated?.();
  };

  return (
    <Card data-testid="nl-composer">
      <label htmlFor="nl-input" className="text-title-sm text-ac-ink block mb-2">
        What should this agent never be allowed to do?
      </label>
      <textarea
        id="nl-input"
        data-testid="nl-input"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="e.g. claims-adjuster may not release a payment over $50,000 without approval"
        className="w-full h-28 rounded-md border border-ac-hairline-strong bg-ac-canvas-soft p-3 text-body-sm text-ac-ink placeholder:text-ac-muted focus:outline focus:outline-2 focus:outline-ac-primary focus:outline-offset-2"
      />
      <div className="mt-3">
        <Button label="Draft policy" onClick={handleDraft} disabled={!value.trim()} />
      </div>

      {draft && (
        <div className="mt-4">
          <DraftReview draft={draft} onSimulate={handleSimulate} onActivate={handleActivate} />
        </div>
      )}

      {simulation && (
        <div className="mt-4">
          <SimulationResult result={simulation} />
        </div>
      )}
    </Card>
  );
}
