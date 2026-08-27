import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAgents, COVERAGE_LABEL } from "@/api/agents";
import type { Agent } from "@/api/agents";
import { EmptyState } from "@/components/primitives/EmptyState";

// The state this whole coverage feature exists to surface: the library
// loaded and the hook bound, but no call ever arrived. It must be impossible
// to miss on this list, so it gets its own visual weight -- not a quiet grey.
const COVERAGE_STYLE: Record<Agent["coverage_state"], string> = {
  governed: "bg-ac-decision-allow-soft text-ac-decision-allow",
  installed_not_firing: "bg-ac-surface-sunk text-ac-warning border border-ac-warning",
  unknown: "bg-ac-surface-sunk text-ac-muted",
};

function slug(name: string): string {
  return name;
}

function AgentRow({ agent }: { agent: Agent }) {
  return (
    <Link
      to={`/agents/${agent.id}`}
      data-testid={`agent-row-${slug(agent.name)}`}
      className="grid grid-cols-[1.4fr_1fr_1fr_1fr_1.4fr] items-start gap-4 px-4 py-3 border-b border-ac-hairline-soft hover:bg-ac-surface-sunk transition-colors"
    >
      <div className="min-w-0">
        <p className="text-body-md text-ac-body-strong truncate">{agent.name}</p>
        <p className="text-caption text-ac-muted truncate">{agent.workflow ?? "unassigned"}</p>
      </div>
      <div className="min-w-0 text-body-sm text-ac-body truncate">{agent.framework ?? "—"}</div>
      <div className="min-w-0 text-identifier text-ac-muted truncate">{agent.hook ?? "—"}</div>
      <div className="min-w-0" data-testid={`coverage-${agent.id}`}>
        <span
          className={`inline-flex items-center rounded-full px-[10px] py-[3px] text-label-uc ${COVERAGE_STYLE[agent.coverage_state]}`}
        >
          {COVERAGE_LABEL[agent.coverage_state]}
        </span>
      </div>
      <div className="min-w-0 text-caption text-ac-warning space-y-0.5">
        {agent.silent_noop_warnings.map((w) => (
          <p key={w} className="truncate">{w}</p>
        ))}
        {agent.unresolved_systems.map((s) => (
          <p key={s} className="truncate">Unresolved system: {s}</p>
        ))}
      </div>
    </Link>
  );
}

export function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listAgents()
      .then(setAgents)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-title-lg text-ac-ink">Agents</h1>

      {loading ? (
        <div className="h-40 bg-ac-surface-sunk rounded-lg animate-pulse" />
      ) : agents.length === 0 ? (
        <EmptyState title="No agents connected yet — install the SDK and it registers itself." />
      ) : (
        <div
          data-testid="agents-table"
          className="border border-ac-hairline rounded-lg bg-ac-surface-card overflow-y-auto max-h-[70vh]"
        >
          <div
            className="grid grid-cols-[1.4fr_1fr_1fr_1fr_1.4fr] gap-4 px-4 py-2.5 text-label-uc text-ac-muted border-b border-ac-hairline bg-ac-surface-sunk"
          >
            <div>Agent</div>
            <div>Framework</div>
            <div>Hook</div>
            <div>Coverage</div>
            <div>Flags</div>
          </div>
          {agents.map((a) => (
            <AgentRow key={a.id} agent={a} />
          ))}
        </div>
      )}
    </div>
  );
}
