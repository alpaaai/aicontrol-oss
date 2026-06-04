import { useState } from "react";
import { X, Plus } from "lucide-react";
import type { ToolDenylistFormState, NumericConditionRow, NumericOp } from "./conditionUtils";

interface Props {
  data: ToolDenylistFormState;
  onChange: (data: ToolDenylistFormState) => void;
}

const inputCls =
  "border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 bg-white";

const OPS: NumericOp[] = [">", ">=", "<", "<=", "=="];

export function ToolDenylistForm({ data, onChange }: Props) {
  const [draft, setDraft] = useState("");

  const addTool = () => {
    const trimmed = draft.trim();
    if (!trimmed || data.blocked_tools.includes(trimmed)) return;
    onChange({ ...data, blocked_tools: [...data.blocked_tools, trimmed] });
    setDraft("");
  };

  const removeTool = (tool: string) => {
    onChange({ ...data, blocked_tools: data.blocked_tools.filter((t) => t !== tool) });
  };

  const numericRows = data.numericConditions ?? [];

  const updateNumericRow = (i: number, row: NumericConditionRow) => {
    const rows = [...numericRows];
    rows[i] = row;
    onChange({ ...data, numericConditions: rows });
  };

  const removeNumericRow = (i: number) => {
    onChange({ ...data, numericConditions: numericRows.filter((_, idx) => idx !== i) });
  };

  const addNumericRow = () => {
    onChange({ ...data, numericConditions: [...numericRows, { field: "", op: ">", value: 0 }] });
  };

  const paramEntries = Object.entries(data.parameterMatch ?? {});

  return (
    <div className="space-y-4">
      {/* Blocked tools */}
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

      {/* Numeric conditions */}
      <div className="space-y-2 border-t border-ac-border pt-3">
        <p className="text-[12px] font-medium text-ac-text-primary">
          Numeric conditions{" "}
          <span className="text-[11px] font-normal text-ac-text-muted">(AND with tool name)</span>
        </p>
        <p className="text-[11px] text-ac-text-muted">
          All rows must pass. Leave empty to match any call to the blocked tools.
        </p>

        {numericRows.map((row, i) => (
          <div key={i} className="flex gap-2 items-end">
            <div className="flex-1">
              {i === 0 && (
                <label className="text-[11px] text-ac-text-muted block mb-1">Parameter</label>
              )}
              <input
                value={row.field}
                onChange={(e) => updateNumericRow(i, { ...row, field: e.target.value })}
                placeholder="e.g. amount, limit"
                className={`w-full ${inputCls}`}
                data-testid={`denylist-numeric-field-${i}`}
              />
            </div>
            <div className="w-20">
              {i === 0 && (
                <label className="text-[11px] text-ac-text-muted block mb-1">Op</label>
              )}
              <select
                value={row.op}
                onChange={(e) => updateNumericRow(i, { ...row, op: e.target.value as NumericOp })}
                className={`w-full ${inputCls}`}
              >
                {OPS.map((op) => (
                  <option key={op} value={op}>{op}</option>
                ))}
              </select>
            </div>
            <div className="w-28">
              {i === 0 && (
                <label className="text-[11px] text-ac-text-muted block mb-1">Value</label>
              )}
              <input
                type="number"
                value={row.value}
                onChange={(e) => updateNumericRow(i, { ...row, value: Number(e.target.value) })}
                className={`w-full ${inputCls}`}
              />
            </div>
            <button
              type="button"
              onClick={() => removeNumericRow(i)}
              className="pb-2 text-ac-text-muted hover:text-ac-deny"
              aria-label="Remove numeric row"
            >
              <X size={14} />
            </button>
          </div>
        ))}

        <button
          type="button"
          onClick={addNumericRow}
          className="flex items-center gap-1 text-[12px] text-ac-primary hover:text-ac-primary/80"
        >
          <Plus size={12} /> Add numeric condition
        </button>
      </div>

      {/* Parameter filters (read-only pass-through) */}
      {paramEntries.length > 0 && (
        <div className="border-t border-ac-border pt-3">
          <p className="text-[12px] font-medium text-ac-text-primary mb-1">
            Parameter filters{" "}
            <span className="text-[11px] font-normal text-ac-text-muted">(read-only — edit in JSON mode)</span>
          </p>
          <div className="flex flex-wrap gap-1.5">
            {paramEntries.map(([key, val]) => (
              <span
                key={key}
                className="text-[12px] font-mono bg-amber-50 text-amber-800 border border-amber-200 px-2 py-0.5 rounded"
              >
                {key}={String(val ?? "null")}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
