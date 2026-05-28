import { useState } from "react";
import type { AuditFilters as Filters } from "@/api/auditEvents";

interface Props {
  onFilter: (f: Filters) => void;
}

export function AuditFilters({ onFilter }: Props) {
  const [decision, setDecision] = useState("");
  const [toolName, setToolName] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const apply = () =>
    onFilter({
      decision: decision || undefined,
      tool_name: toolName || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      limit: 50,
      offset: 0,
    });

  const reset = () => {
    setDecision("");
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
