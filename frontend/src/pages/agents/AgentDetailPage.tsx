import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getAgent, getAgentPolicies, updateAgentGovernanceMode, COVERAGE_LABEL } from "@/api/agents";
import type { AgentDetail } from "@/api/agents";
import type { PolicyScope } from "@/api/policies";
import { PolicySentence } from "@/components/primitives/PolicySentence";
import { EmptyState } from "@/components/primitives/EmptyState";

// One object per screen, full width, generous measure -- the direct answer
// to "I can't tell which policy fires when."
export function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [policies, setPolicies] = useState<PolicyScope[] | null>(null);
  const [policiesError, setPoliciesError] = useState(false);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [agentLoading, setAgentLoading] = useState(true);
  const [switchingMode, setSwitchingMode] = useState(false);

  const handleToggleGovernanceMode = async () => {
    if (!agent) return;
    const next = agent.governance_mode === "govern" ? "observe" : "govern";
    setSwitchingMode(true);
    try {
      const updated = await updateAgentGovernanceMode(agent.id, next);
      setAgent(updated);
    } finally {
      setSwitchingMode(false);
    }
  };

  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    async function load() {
      setAgentLoading(true);
      setAgentError(null);
      try {
        const a = await getAgent(id!);
        if (!cancelled) setAgent(a);
      } catch {
        if (!cancelled) {
          setAgentError("Couldn't load this agent. It may have been removed, or there's a connection problem.");
        }
      } finally {
        if (!cancelled) setAgentLoading(false);
      }
    }
    load();
    setPoliciesError(false);
    getAgentPolicies(id).then(setPolicies).catch(() => {
      setPolicies([]);
      setPoliciesError(true);
    });

    return () => {
      cancelled = true;
    };
  }, [id]);

  if (agentLoading) {
    return (
      <div className="p-6 max-w-3xl">
        <div className="h-24 bg-ac-surface-sunk rounded-lg animate-pulse" />
      </div>
    );
  }

  if (agentError || !agent) {
    return (
      <div className="p-6 max-w-3xl">
        <Link to="/agents" className="text-body-sm text-ac-muted hover:text-ac-ink">
          &larr; Agents
        </Link>
        <EmptyState title={agentError ?? "Agent not found."} />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-8 max-w-3xl">
      <div>
        <Link to="/agents" className="text-body-sm text-ac-muted hover:text-ac-ink">
          &larr; Agents
        </Link>
        <h1 className="text-title-lg text-ac-ink mt-1">{agent?.name ?? "—"}</h1>
        <p className="text-body-sm text-ac-muted mt-0.5">
          {agent?.workflow ?? "unassigned"}
        </p>
      </div>

      {agent && (
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center rounded-full px-[10px] py-[3px] text-label-uc ${
              agent.governance_mode === "govern"
                ? "bg-ac-decision-allow-soft text-ac-decision-allow"
                : "bg-ac-surface-sunk text-ac-warning border border-ac-warning"
            }`}
          >
            {agent.governance_mode === "govern" ? "Enforcing" : "Observe only — not enforcing"}
          </span>
          <button
            onClick={handleToggleGovernanceMode}
            disabled={switchingMode}
            className="text-body-sm text-ac-primary hover:underline disabled:opacity-50"
          >
            {switchingMode
              ? "Switching…"
              : agent.governance_mode === "govern"
                ? "Switch to observe"
                : "Switch to govern"}
          </button>
        </div>
      )}

      {agent && (
        <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-body-sm">
          <div>
            <dt className="text-ac-muted">Framework</dt>
            <dd className="text-ac-body-strong">{agent.framework ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-ac-muted">Hook</dt>
            <dd className="text-identifier text-ac-body-strong">{agent.hook ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-ac-muted">Coverage</dt>
            <dd className="text-ac-body-strong">{COVERAGE_LABEL[agent.coverage_state]}</dd>
          </div>
          <div>
            <dt className="text-ac-muted">SDK version</dt>
            <dd className="text-ac-body-strong">{agent.sdk_version ?? "—"}</dd>
          </div>
        </dl>
      )}

      {agent && (agent.silent_noop_warnings.length > 0 || agent.unresolved_systems.length > 0) && (
        <div className="border border-ac-warning rounded-lg p-4 space-y-1">
          {agent.silent_noop_warnings.map((w) => (
            <p key={w} className="text-body-sm text-ac-warning">{w}</p>
          ))}
          {agent.unresolved_systems.map((s) => (
            <p key={s} className="text-body-sm text-ac-warning">Unresolved system: {s}</p>
          ))}
        </div>
      )}

      <div>
        <h2 className="text-title-md text-ac-ink mb-3">Policies governing this agent</h2>
        <div data-testid="governing-policies" className="space-y-4">
          {policies === null ? (
            <div className="h-20 bg-ac-surface-sunk rounded-lg animate-pulse" />
          ) : policiesError ? (
            <EmptyState title="Couldn't load policies for this agent. Try refreshing the page." />
          ) : policies.length === 0 ? (
            <EmptyState title="No policies govern this agent yet — describe one in plain English." />
          ) : (
            policies.map((p) => (
              <div key={p.id} className="border border-ac-hairline rounded-lg p-4 bg-ac-surface-card">
                <PolicySentence policy={p} variant="inline" />
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
