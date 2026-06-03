import { useState } from "react";
import { X } from "lucide-react";
import type { ToolPatternFormState } from "./conditionUtils";

interface Props {
  data: ToolPatternFormState;
  onChange: (data: ToolPatternFormState) => void;
}

const inputCls =
  "border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 bg-white";

export function ToolPatternForm({ data, onChange }: Props) {
  const [draft, setDraft] = useState("");

  const addPattern = () => {
    const p = draft.trim();
    if (!p || data.patterns.includes(p)) return;
    onChange({ patterns: [...data.patterns, p] });
    setDraft("");
  };

  const removePattern = (pattern: string) => {
    onChange({ patterns: data.patterns.filter((p) => p !== pattern) });
  };

  return (
    <div className="space-y-3">
      <p className="text-[12px] text-ac-text-muted">
        Match tool calls whose name contains any of the substrings below. Example: <code className="text-[11px] bg-gray-100 px-1 rounded">write</code> catches <code className="text-[11px] bg-gray-100 px-1 rounded">write_file</code>, <code className="text-[11px] bg-gray-100 px-1 rounded">write_record</code>, etc.
      </p>

      <div className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addPattern();
            }
          }}
          placeholder="substring — press Enter to add"
          className={`flex-1 ${inputCls}`}
          data-testid="tool-pattern-input"
        />
        <button
          type="button"
          onClick={addPattern}
          className="px-3 py-2 text-sm bg-ac-primary text-white rounded-lg hover:bg-ac-primary/90"
        >
          Add
        </button>
      </div>

      {data.patterns.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {data.patterns.map((p) => (
            <span
              key={p}
              className="inline-flex items-center gap-1 text-[12px] font-mono bg-ac-review-bg text-ac-review px-2 py-0.5 rounded-full"
            >
              {p}
              <button
                type="button"
                onClick={() => removePattern(p)}
                aria-label={`Remove ${p}`}
              >
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
      )}

      {data.patterns.length === 0 && (
        <p className="text-[11px] text-ac-text-muted italic">
          No patterns added yet. Add at least one substring to match.
        </p>
      )}
    </div>
  );
}
