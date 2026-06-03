import { X, Plus } from "lucide-react";
import type { ParameterMatchFormState, ParamMatchRow, ParamMatchOperator } from "./conditionUtils";

interface Props {
  data: ParameterMatchFormState;
  onChange: (data: ParameterMatchFormState) => void;
}

const inputCls =
  "border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 bg-white";

const OPERATORS: { value: ParamMatchOperator; label: string }[] = [
  { value: "contains", label: "contains" },
  { value: "equals", label: "equals" },
];

function RowEditor({
  row,
  index,
  onChange,
  onRemove,
}: {
  row: ParamMatchRow;
  index: number;
  onChange: (row: ParamMatchRow) => void;
  onRemove: () => void;
}) {
  const addValue = (draft: string) => {
    const trimmed = draft.trim();
    if (!trimmed) return;
    onChange({ ...row, values: [...row.values.filter(Boolean), trimmed] });
  };

  const removeValue = (val: string) => {
    onChange({ ...row, values: row.values.filter((v) => v !== val) });
  };

  return (
    <div className="border border-ac-border rounded-lg p-3 space-y-2 bg-white">
      <div className="flex gap-2 items-center">
        <div className="flex-1">
          <label className="text-[11px] text-ac-text-muted block mb-1">Parameter key</label>
          <input
            value={row.key}
            onChange={(e) => onChange({ ...row, key: e.target.value })}
            placeholder='e.g. path, url, id — or * for any parameter'
            className={`w-full ${inputCls}`}
            data-testid={`param-key-${index}`}
          />
        </div>
        <div className="w-32">
          <label className="text-[11px] text-ac-text-muted block mb-1">Operator</label>
          <select
            value={row.operator}
            onChange={(e) =>
              onChange({ ...row, operator: e.target.value as ParamMatchOperator, values: [""] })
            }
            className={`w-full ${inputCls}`}
          >
            {OPERATORS.map((op) => (
              <option key={op.value} value={op.value}>{op.label}</option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={onRemove}
          className="mt-4 text-ac-text-muted hover:text-ac-deny"
          aria-label="Remove row"
        >
          <X size={14} />
        </button>
      </div>

      {row.operator === "contains" ? (
        <div>
          <label className="text-[11px] text-ac-text-muted block mb-1">
            Match values (press Enter to add each)
          </label>
          <ValueTagInput
            values={row.values.filter(Boolean)}
            placeholder="pattern — press Enter"
            onAdd={addValue}
            onRemove={removeValue}
          />
        </div>
      ) : (
        <div>
          <label className="text-[11px] text-ac-text-muted block mb-1">Exact value</label>
          <input
            value={row.values[0] ?? ""}
            onChange={(e) => onChange({ ...row, values: [e.target.value] })}
            placeholder='e.g. * or null'
            className={`w-full ${inputCls}`}
          />
        </div>
      )}
    </div>
  );
}

function ValueTagInput({
  values,
  placeholder,
  onAdd,
  onRemove,
}: {
  values: string[];
  placeholder: string;
  onAdd: (v: string) => void;
  onRemove: (v: string) => void;
}) {
  let draft = "";
  return (
    <div className="space-y-1.5">
      <input
        placeholder={placeholder}
        className={`w-full ${inputCls}`}
        onChange={(e) => { draft = e.target.value; }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            onAdd((e.target as HTMLInputElement).value);
            (e.target as HTMLInputElement).value = "";
            draft = "";
          }
        }}
      />
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {values.map((v) => (
            <span
              key={v}
              className="inline-flex items-center gap-1 text-[11px] font-mono bg-gray-100 text-ac-text-primary px-2 py-0.5 rounded-full"
            >
              {v}
              <button type="button" onClick={() => onRemove(v)} aria-label={`Remove ${v}`}>
                <X size={9} />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function ParameterMatchForm({ data, onChange }: Props) {
  const updateRow = (index: number, row: ParamMatchRow) => {
    const rows = [...data.rows];
    rows[index] = row;
    onChange({ rows });
  };

  const removeRow = (index: number) => {
    onChange({ rows: data.rows.filter((_, i) => i !== index) });
  };

  const addRow = () => {
    onChange({
      rows: [...data.rows, { key: "", operator: "contains", values: [""] }],
    });
  };

  return (
    <div className="space-y-2">
      <p className="text-[12px] text-ac-text-muted">
        Block or review calls where a parameter value matches. Use <code className="text-[11px] bg-gray-100 px-1 rounded">*</code> as the key to check all parameters.
        Multiple rows use OR logic — any match fires the policy.
      </p>

      {data.rows.map((row, i) => (
        <RowEditor
          key={i}
          row={row}
          index={i}
          onChange={(r) => updateRow(i, r)}
          onRemove={() => removeRow(i)}
        />
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
