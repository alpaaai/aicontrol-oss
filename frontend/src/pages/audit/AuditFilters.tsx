import { useState, useEffect, useRef } from "react";
import type { AuditFilters as Filters } from "@/api/auditEvents";
import { listAgents } from "@/api/agents";
import type { Agent } from "@/api/agents";

interface Props {
  onFilter: (f: Filters) => void;
}

export function AuditFilters({ onFilter }: Props) {
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

  const filteredAgents = agents.filter((a) =>
    a.name.toLowerCase().includes(agentSearch.toLowerCase())
  );

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
    <div className="flex flex-wrap gap-3 items-end mb-4">
      <div>
        <label className="text-[11px] text-ac-text-muted block mb-1">Decision</label>
        <select
          value={decision}
          onChange={(e) => setDecision(e.target.value)}
          className="border border-ac-border rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 bg-white"
        >
          <option value="">All</option>
          <option value="allow">Allow</option>
          <option value="deny">Deny</option>
          <option value="review">Review</option>
        </select>
      </div>

      {/* Agent searchable dropdown */}
      <div ref={agentRef} className="relative">
        <label className="text-[11px] text-ac-text-muted block mb-1">Agent</label>
        <input
          value={agentId ? (selectedAgent?.name ?? agentSearch) : agentSearch}
          onChange={(e) => {
            setAgentSearch(e.target.value);
            setAgentId("");
            setAgentOpen(true);
          }}
          onFocus={() => setAgentOpen(true)}
          placeholder="All agents"
          className="border border-ac-border rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 w-44"
        />
        {agentOpen && filteredAgents.length > 0 && (
          <div className="absolute z-20 top-full mt-1 left-0 w-44 bg-white border border-ac-border rounded-lg shadow-lg overflow-y-auto max-h-48 [scrollbar-width:thin]">
            {agentId && (
              <button
                onClick={() => selectAgent(null)}
                className="w-full text-left px-3 py-2 text-[12px] text-ac-text-muted hover:bg-gray-50 border-b border-gray-100"
              >
                Clear
              </button>
            )}
            {filteredAgents.map((a) => (
              <button
                key={a.id}
                onClick={() => selectAgent(a)}
                className={`w-full text-left px-3 py-2 text-[12px] hover:bg-gray-50 ${
                  a.id === agentId ? "text-ac-primary font-medium" : "text-ac-text-primary"
                }`}
              >
                {a.name}
              </button>
            ))}
          </div>
        )}
      </div>

      <div>
        <label className="text-[11px] text-ac-text-muted block mb-1">Tool name</label>
        <input
          value={toolName}
          onChange={(e) => setToolName(e.target.value)}
          placeholder="e.g. read_file"
          className="border border-ac-border rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20"
        />
      </div>

      <div>
        <label className="text-[11px] text-ac-text-muted block mb-1">From</label>
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          className="border border-ac-border rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20"
        />
      </div>
      <div>
        <label className="text-[11px] text-ac-text-muted block mb-1">To</label>
        <input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          className="border border-ac-border rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20"
        />
      </div>

      <button
        onClick={apply}
        className="bg-ac-primary text-white rounded-lg px-4 py-1.5 text-sm font-medium hover:bg-ac-primary/90"
      >
        Apply
      </button>
      <button
        onClick={reset}
        className="text-sm text-ac-text-muted hover:text-ac-text-primary px-2"
      >
        Reset
      </button>
    </div>
  );
}
