import { Plus, X } from "lucide-react";
import type { NumericConditionsFormState, NumericConditionRow, NumericOp } from "./conditionUtils";

interface Props {
  data: NumericConditionsFormState;
  onChange: (data: NumericConditionsFormState) => void;
}

const inputCls =
  "border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 bg-white";

const OPS: NumericOp[] = [">", ">=", "<", "<=", "=="];

export function NumericConditionsForm({ data, onChange }: Props) {
  const updateRow = (index: number, row: NumericConditionRow) => {
    const rows = [...data.rows];
    rows[index] = row;
    onChange({ rows });
  };

  const removeRow = (index: number) => {
    onChange({ rows: data.rows.filter((_, i) => i !== index) });
  };

  const addRow = () => {
    onChange({ rows: [...data.rows, { field: "", op: ">", value: 0 }] });
  };

  return (
    <div className="space-y-2">
      <p className="text-[12px] text-ac-text-muted">
        Match tool calls based on numeric parameter values. Multiple rows use OR logic — any match fires the policy.
      </p>

      {data.rows.map((row, i) => (
        <div key={i} className="flex gap-2 items-end">
          <div className="flex-1">
            {i === 0 && (
              <label className="text-[11px] text-ac-text-muted block mb-1">
                Parameter name
              </label>
            )}
            <input
              value={row.field}
              onChange={(e) => updateRow(i, { ...row, field: e.target.value })}
              placeholder="e.g. amount, limit, count"
              className={`w-full ${inputCls}`}
              data-testid={`numeric-field-${i}`}
            />
          </div>
          <div className="w-20">
            {i === 0 && (
              <label className="text-[11px] text-ac-text-muted block mb-1">Op</label>
            )}
            <select
              value={row.op}
              onChange={(e) => updateRow(i, { ...row, op: e.target.value as NumericOp })}
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
              onChange={(e) => updateRow(i, { ...row, value: Number(e.target.value) })}
              className={`w-full ${inputCls}`}
              data-testid={`numeric-value-${i}`}
            />
          </div>
          <button
            type="button"
            onClick={() => removeRow(i)}
            className="pb-2 text-ac-text-muted hover:text-ac-deny"
            aria-label="Remove row"
          >
            <X size={14} />
          </button>
        </div>
      ))}

      <button
        type="button"
        onClick={addRow}
        className="flex items-center gap-1 text-[12px] text-ac-primary hover:text-ac-primary/80"
      >
        <Plus size={12} /> Add condition row
      </button>
    </div>
  );
}
