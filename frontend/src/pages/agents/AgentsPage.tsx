import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAgents, COVERAGE_LABEL } from "@/api/agents";
import type { Agent } from "@/api/agents";
import { EmptyState } from "@/components/primitives/EmptyState";
import { useAuth } from "@/hooks/useAuth";
import { RegisterAgentDialog } from "./RegisterAgentDialog";

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
        <span
          data-testid={`governance-mode-${agent.id}`}
          className={`inline-flex items-center rounded-full px-[8px] py-[1px] mt-1 text-[10px] uppercase tracking-wide ${
            agent.governance_mode === "govern"
              ? "bg-ac-decision-allow-soft text-ac-decision-allow"
              : "bg-ac-surface-sunk text-ac-warning border border-ac-warning"
          }`}
        >
          {agent.governance_mode === "govern" ? "Enforcing" : "Observe only — not enforcing"}
        </span>
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
  const [loadError, setLoadError] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const refresh = () => {
    setLoading(true);
    setLoadError(false);
    return listAgents()
      .then(setAgents)
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-title-lg text-ac-ink">Agents</h1>
        {isAdmin && (
          <button
            onClick={() => setDialogOpen(true)}
            className="bg-ac-primary text-white rounded-lg px-4 py-2 text-sm font-medium"
          >
            Register new agent
          </button>
        )}
      </div>

      <RegisterAgentDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onRegistered={refresh}
      />

      {loading ? (
        <div className="h-40 bg-ac-surface-sunk rounded-lg animate-pulse" />
      ) : loadError ? (
        <p className="text-body-sm text-ac-error py-8 text-center">
          Couldn't load agents. Try refreshing the page.
        </p>
      ) : agents.length === 0 ? (
        <EmptyState title={`No agents connected yet — register one with scripts/onboard_agent.py${isAdmin ? ", use the Register new agent button above," : ""} or issue an agent token and let the SDK self-register.`} />
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
