import { PolicySentence } from "@/components/primitives/PolicySentence";
import { Button } from "@/components/primitives/Button";
import { draftToPolicyScope, type NLDraftResponse } from "@/api/policies";

// The middle state of the describe -> draft -> simulate -> activate loop
// (spec §6.1). A drafted policy renders as the display-variant policy
// sentence with editable chips -- never JSON, never Cedar. A draft that
// could not be compiled explains itself in plain language instead.
export function DraftReview(props: {
  draft: NLDraftResponse;
  onSimulate: () => void;
  onActivate: () => void;
}) {
  const { draft } = props;

  if (draft.status === "requires_manual_authoring" || !draft.draft) {
    return (
      <div data-testid="draft-review" className="text-body-sm text-ac-body">
        {draft.warnings[0] ?? "This description needs manual authoring."}
      </div>
    );
  }

  const scope = draftToPolicyScope(draft.draft);

  return (
    <div data-testid="draft-review" className="space-y-4">
      <PolicySentence policy={scope} variant="display" editable />
      <div className="flex gap-2">
        <Button variant="secondary" label="Simulate" onClick={props.onSimulate} />
        <Button label="Activate" pendingLabel="Activating…" doneLabel="Activated" onClick={props.onActivate} />
      </div>
    </div>
  );
}
