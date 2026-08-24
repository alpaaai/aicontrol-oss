import type { WorkflowOutcomes } from "@/api/dashboard";

const OUTCOME_PHRASE: Record<string, (count: number) => string> = {
  payment_held: (n) => `${n} payment${n === 1 ? "" : "s"} held for approval`,
  record_access_denied: (n) => `${n} record access${n === 1 ? "" : "es"} denied`,
  export_blocked: (n) => `${n} export${n === 1 ? "" : "s"} blocked`,
  action_blocked: (n) => `${n} other action${n === 1 ? "" : "s"} blocked`,
};

function workflowLabel(workflow: string): string {
  return workflow === "unassigned"
    ? "unassigned activity"
    : `the ${workflow.replace(/_/g, " ")} process`;
}

function WorkflowSentence({ group }: { group: WorkflowOutcomes }) {
  const clauses = group.outcomes.map((o) => OUTCOME_PHRASE[o.kind]?.(o.count) ?? `${o.count} actions flagged`);
  return (
    <p data-testid="workflow-group" className="text-body-md text-ac-body">
      In {workflowLabel(group.workflow)}, {group.agents} agent{group.agents === 1 ? "" : "s"} made{" "}
      {group.calls.toLocaleString()} tool call{group.calls === 1 ? "" : "s"} this window.{" "}
      {clauses.length > 0 ? clauses.join(". ") + "." : "Nothing was held or denied."}
    </p>
  );
}

export function OutcomeSummary({ workflows }: { workflows: WorkflowOutcomes[] }) {
  if (workflows.length === 0) {
    return (
      <div data-testid="outcome-summary">
        <p className="text-title-lg text-ac-muted">
          No governed activity yet -- once agents start calling tools, what governance did shows up here.
        </p>
      </div>
    );
  }

  return (
    <div data-testid="outcome-summary" className="space-y-3">
      {workflows.map((group) => (
        <WorkflowSentence key={group.workflow} group={group} />
      ))}
    </div>
  );
}
