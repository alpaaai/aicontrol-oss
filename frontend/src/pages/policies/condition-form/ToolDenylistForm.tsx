import { useState } from "react";
import { X } from "lucide-react";
import type { ToolDenylistFormState } from "./conditionUtils";

interface Props {
  data: ToolDenylistFormState;
  onChange: (data: ToolDenylistFormState) => void;
}

const inputCls =
  "border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 bg-white";

export function ToolDenylistForm({ data, onChange }: Props) {
  const [draft, setDraft] = useState("");

  const addTool = () => {
    const trimmed = draft.trim();
    if (!trimmed || data.blocked_tools.includes(trimmed)) return;
    onChange({ blocked_tools: [...data.blocked_tools, trimmed] });
    setDraft("");
  };

  const removeTool = (tool: string) => {
    onChange({ blocked_tools: data.blocked_tools.filter((t) => t !== tool) });
  };

  return (
    <div className="space-y-3">
      <p className="text-[12px] text-ac-text-muted">
        Block any tool call whose name exactly matches one of the entries below.
      </p>

      <div className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addTool();
            }
          }}
          placeholder="tool_name — press Enter to add"
          className={`flex-1 ${inputCls}`}
          data-testid="tool-denylist-input"
        />
        <button
          type="button"
          onClick={addTool}
          className="px-3 py-2 text-sm bg-ac-primary text-white rounded-lg hover:bg-ac-primary/90"
        >
          Add
        </button>
      </div>

      {data.blocked_tools.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {data.blocked_tools.map((tool) => (
            <span
              key={tool}
              className="inline-flex items-center gap-1 text-[12px] font-mono bg-ac-deny-bg text-ac-deny px-2 py-0.5 rounded-full"
            >
              {tool}
              <button
                type="button"
                onClick={() => removeTool(tool)}
                className="hover:text-ac-deny/70"
                aria-label={`Remove ${tool}`}
              >
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
      )}

      {data.blocked_tools.length === 0 && (
        <p className="text-[11px] text-ac-text-muted italic">
          No tools blocked yet. Add at least one tool name.
        </p>
      )}
    </div>
  );
}
