import { useState, useEffect } from "react";
import { listAgents } from "@/api/agents";
import type { Agent } from "@/api/agents";
import { listPolicies } from "@/api/policies";
import type { Policy } from "@/api/policies";
import { AgentTable } from "./AgentTable";
import { AgentDetailPanel } from "./AgentDetailPanel";

export function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [selected, setSelected] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    Promise.all([listAgents(), listPolicies()])
      .then(([a, p]) => {
        setAgents(a);
        setPolicies(p);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const handleUpdated = () => {
    load();
  };

  return (
    <div className="flex h-full">
      <div className="flex-1 flex flex-col min-w-0 p-6">
        <div className="mb-5">
          <h2 className="text-[18px] font-semibold tracking-[-0.02em] text-ac-text-primary">
            Agents
          </h2>
          <p className="text-sm text-ac-text-muted mt-0.5">
            {loading
              ? "—"
              : `${agents.length} registered · click an agent to manage tools`}
          </p>
        </div>
        {loading ? (
          <div className="h-40 bg-gray-50 rounded animate-pulse" />
        ) : (
          <AgentTable
            agents={agents}
            selectedId={selected?.id ?? null}
            onSelect={setSelected}
          />
        )}
      </div>

      {selected && (
        <AgentDetailPanel
          agent={selected}
          policies={policies}
          onUpdated={handleUpdated}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
