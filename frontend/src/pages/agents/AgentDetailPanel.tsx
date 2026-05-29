import { useState } from "react";
import type { Agent } from "@/api/agents";
import { patchApprovedTools, computeToolCoverage } from "@/api/agents";
import type { Policy } from "@/api/policies";
import { ToolCoverageRow } from "./ToolCoverageRow";
import { X, Plus, Save } from "lucide-react";

interface Props {
  agent: Agent;
  policies: Policy[];
  onUpdated: () => void;
  onClose: () => void;
}

export function AgentDetailPanel({
  agent,
  policies,
  onUpdated,
  onClose,
}: Props) {
  const [tools, setTools] = useState<string[]>(agent.approved_tools);
  const [newTool, setNewTool] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const coverage = computeToolCoverage(
    tools,
    policies.map((p) => ({ name: p.name, condition: p.condition }))
  );

  const addTool = () => {
    const trimmed = newTool.trim();
    if (trimmed && !tools.includes(trimmed)) {
      setTools([...tools, trimmed]);
      setNewTool("");
    }
  };

  const removeTool = (t: string) => setTools(tools.filter((x) => x !== t));

  const handleSave = async () => {
    setSaving(true);
    await patchApprovedTools(agent.id, tools);
    setSaved(true);
    setSaving(false);
    setTimeout(() => setSaved(false), 2000);
    onUpdated();
  };

  const dirty =
    JSON.stringify([...tools].sort()) !==
    JSON.stringify([...agent.approved_tools].sort());

  return (
    <div className="w-[340px] shrink-0 border-l border-ac-border bg-ac-card flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-ac-border">
        <h3 className="text-[14px] font-semibold text-ac-text-primary truncate">
          {agent.name}
        </h3>
        <button
          onClick={onClose}
          className="text-ac-text-muted hover:text-ac-text-primary"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="space-y-1.5">
          {(
            [
              ["Status", agent.status],
              ["Owner", agent.owner ?? "—"],
              ["Framework", agent.framework ?? "—"],
              ["Model", agent.model_version ?? "—"],
            ] as [string, string][]
          ).map(([label, val]) => (
            <div key={label} className="flex justify-between text-[13px]">
              <span className="text-ac-text-muted">{label}</span>
              <span
                className={`font-medium ${
                  val === "active"
                    ? "text-ac-allow"
                    : val === "suspended"
                    ? "text-ac-deny"
                    : "text-ac-text-primary"
                }`}
              >
                {val}
              </span>
            </div>
          ))}
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-[12px] font-medium text-ac-text-primary">
              Approved tools
            </p>
            {dirty && (
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1 text-[11px] bg-ac-primary text-white px-2.5 py-1 rounded-md disabled:opacity-50"
              >
                <Save size={10} />{" "}
                {saving ? "Saving…" : saved ? "Saved ✓" : "Save"}
              </button>
            )}
          </div>

          <div className="space-y-0.5 mb-2">
            {tools.map((t) => (
              <div key={t} className="flex items-center gap-2 group">
                <span className="font-mono text-[12px] text-ac-text-primary flex-1">
                  {t}
                </span>
                <button
                  onClick={() => removeTool(t)}
                  className="opacity-0 group-hover:opacity-100 text-ac-text-muted hover:text-ac-deny transition-all"
                >
                  <X size={11} />
                </button>
              </div>
            ))}
          </div>

          <div className="flex gap-1.5">
            <input
              value={newTool}
              onChange={(e) => setNewTool(e.target.value)}
              onKeyDown={(e) =>
                e.key === "Enter" && (e.preventDefault(), addTool())
              }
              placeholder="tool_name"
              className="flex-1 border border-ac-border rounded-md px-2.5 py-1.5 text-[12px] font-mono outline-none focus:ring-2 focus:ring-ac-primary/20"
            />
            <button
              onClick={addTool}
              className="border border-ac-border rounded-md px-2.5 py-1.5 text-ac-text-muted hover:text-ac-primary hover:border-ac-primary transition-colors"
            >
              <Plus size={13} />
            </button>
          </div>
        </div>

        <div>
          <p className="text-[12px] font-medium text-ac-text-primary mb-1.5">
            Tool coverage
          </p>
          <div>
            {coverage.map((c) => (
              <ToolCoverageRow
                key={c.tool}
                tool={c.tool}
                governed={c.governed}
                policyName={c.policy_name}
              />
            ))}
            {tools.length === 0 && (
              <p className="text-[12px] text-ac-text-muted">
                No approved tools yet
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
