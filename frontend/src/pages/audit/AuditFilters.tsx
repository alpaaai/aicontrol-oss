import { useState, useEffect, useRef } from "react";
import type { AuditFilters as Filters } from "@/api/auditEvents";
import { listAgents } from "@/api/agents";
import type { Agent } from "@/api/agents";

type GroupBy = "none" | "workflow" | "session";

interface Props {
  onFilter: (f: Filters) => void;
  groupBy: GroupBy;
  onGroupByChange: (g: GroupBy) => void;
}

const inputClass =
  "border border-ac-hairline-strong rounded-md px-3 py-1.5 text-body-sm bg-ac-surface-card text-ac-ink " +
  "focus:outline focus:outline-2 focus:outline-ac-primary focus:outline-offset-2";

export function AuditFilters({ onFilter, groupBy, onGroupByChange }: Props) {
  const [decision, setDecision] = useState("");
  const [toolName, setToolName] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentId, setAgentId] = useState("");
  const [agentSearch, setAgentSearch] = useState("");
  const [agentOpen, setAgentOpen] = useState(false);
  const agentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listAgents().then(setAgents).catch(() => {});
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (agentRef.current && !agentRef.current.contains(e.target as Node)) {
        setAgentOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filteredAgents = agents.filter((a) => a.name.toLowerCase().includes(agentSearch.toLowerCase()));
  const selectedAgent = agents.find((a) => a.id === agentId);

  const selectAgent = (a: Agent | null) => {
    setAgentId(a?.id ?? "");
    setAgentSearch(a?.name ?? "");
    setAgentOpen(false);
  };

  const apply = () =>
    onFilter({
      decision: decision || undefined,
      agent_id: agentId || undefined,
      tool_name: toolName || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      limit: 50,
      offset: 0,
    });

  const reset = () => {
    setDecision("");
    setAgentId("");
    setAgentSearch("");
    setToolName("");
    setDateFrom("");
    setDateTo("");
    onFilter({ limit: 50, offset: 0 });
  };

  return (
    <div className="space-y-3 mb-4">
      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="text-caption text-ac-muted block mb-1">Decision</label>
          <select value={decision} onChange={(e) => setDecision(e.target.value)} className={inputClass}>
            <option value="">All</option>
            <option value="allow">Allow</option>
            <option value="deny">Deny</option>
            <option value="review">Review</option>
          </select>
        </div>

        <div ref={agentRef} className="relative">
          <label className="text-caption text-ac-muted block mb-1">Agent</label>
          <input
            value={agentId ? (selectedAgent?.name ?? agentSearch) : agentSearch}
            onChange={(e) => { setAgentSearch(e.target.value); setAgentId(""); setAgentOpen(true); }}
            onFocus={() => setAgentOpen(true)}
            placeholder="All agents"
            className={inputClass + " w-44"}
          />
          {agentOpen && filteredAgents.length > 0 && (
            <div className="absolute z-20 top-full mt-1 left-0 w-44 bg-ac-surface-card border border-ac-hairline rounded-lg overflow-y-auto max-h-48">
              {agentId && (
                <button onClick={() => selectAgent(null)} className="w-full text-left px-3 py-2 text-body-sm text-ac-muted hover:bg-ac-surface-sunk border-b border-ac-hairline">
                  Clear
                </button>
              )}
              {filteredAgents.map((a) => (
                <button
                  key={a.id}
                  onClick={() => selectAgent(a)}
                  className={`w-full text-left px-3 py-2 text-body-sm hover:bg-ac-surface-sunk ${a.id === agentId ? "text-ac-primary-active" : "text-ac-ink"}`}
                >
                  {a.name}
                </button>
              ))}
            </div>
          )}
        </div>

        <div>
          <label className="text-caption text-ac-muted block mb-1">Tool name</label>
          <input value={toolName} onChange={(e) => setToolName(e.target.value)} placeholder="e.g. read_file" className={inputClass} />
        </div>

        <div>
          <label className="text-caption text-ac-muted block mb-1">From</label>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className={inputClass} />
        </div>
        <div>
          <label className="text-caption text-ac-muted block mb-1">To</label>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className={inputClass} />
        </div>

        <button onClick={apply} className="h-9 px-4 rounded-md text-button bg-ac-primary text-ac-on-primary hover:bg-ac-primary-active">
          Apply
        </button>
        <button onClick={reset} className="text-body-sm text-ac-muted hover:text-ac-ink px-2">
          Reset
        </button>
      </div>

      <div className="flex gap-2">
        <span className="text-caption text-ac-muted self-center mr-1">Group by</span>
        {(["none", "workflow", "session"] as GroupBy[]).map((g) => (
          <button
            key={g}
            data-testid={g === "none" ? undefined : `group-by-${g}`}
            onClick={() => onGroupByChange(g)}
            className={`px-3 py-1 rounded-full text-caption border ${
              groupBy === g
                ? "bg-ac-primary-soft text-ac-primary-active border-transparent"
                : "border-ac-hairline-strong text-ac-body hover:bg-ac-surface-sunk"
            }`}
          >
            {g === "none" ? "Flat" : g === "workflow" ? "Workflow" : "Session"}
          </button>
        ))}
      </div>
    </div>
  );
}
