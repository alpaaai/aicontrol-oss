import type { SimulationResult as SimulationResultData } from "@/api/policies";

// The last state before activation. Prose, not a table of deltas -- "would
// have held N of M calls for approval," followed by the matching calls. An
// empty eligible corpus says so explicitly (C9): a confident "0 of 0" reads
// as "this policy is harmless" when really there was nothing to test it
// against, so the corpus_note replaces the count sentence entirely rather
// than sitting beside a zero.
export function SimulationResult(props: { result: SimulationResultData }) {
  const { result } = props;

  if (result.corpus_note) {
    return (
      <div data-testid="simulation-result" className="text-body-sm text-ac-body">
        {result.corpus_note}
      </div>
    );
  }

  return (
    <div data-testid="simulation-result" className="text-body-sm text-ac-body space-y-2">
      <p>
        Would have held {result.would_review} of {result.eligible_events} calls for approval. Here they are.
      </p>
      {result.matches.length > 0 && (
        <ul className="space-y-1">
          {result.matches.map((m) => (
            <li key={m.audit_event_id} className="text-caption text-ac-muted">
              {m.tool_name} — {m.decision}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
