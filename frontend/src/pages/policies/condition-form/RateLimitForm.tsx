import { useState } from "react";
import { X } from "lucide-react";
import type { RateLimitFormState, RateLimitWindow } from "./conditionUtils";

interface Props {
  data: RateLimitFormState;
  onChange: (data: RateLimitFormState) => void;
}

const inputCls =
  "border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 bg-white";

const WINDOWS: { value: RateLimitWindow; label: string }[] = [
  { value: "session", label: "per session" },
  { value: "5m", label: "per 5 minutes" },
  { value: "60m", label: "per hour" },
  { value: "24h", label: "per day" },
  { value: "7d", label: "per week" },
];

export function RateLimitForm({ data, onChange }: Props) {
  const [toolDraft, setToolDraft] = useState("");

  const addTool = () => {
    const t = toolDraft.trim();
    if (!t || data.tools.includes(t)) return;
    onChange({ ...data, tools: [...data.tools, t] });
    setToolDraft("");
  };

  const removeTool = (tool: string) => {
    onChange({ ...data, tools: data.tools.filter((t) => t !== tool) });
  };

  return (
    <div className="space-y-3">
      <p className="text-[12px] text-ac-text-muted">
        Count calls to specific tools and fire when the threshold is exceeded within the window.
      </p>

      <div className="flex gap-3">
        <div className="w-28">
          <label className="text-[12px] text-ac-text-muted block mb-1">Max calls</label>
          <input
            type="number"
            min={1}
            value={data.max_calls}
            onChange={(e) => onChange({ ...data, max_calls: Number(e.target.value) || 1 })}
            className={`w-full ${inputCls}`}
            data-testid="rate-limit-max-calls"
          />
        </div>
        <div className="flex-1">
          <label className="text-[12px] text-ac-text-muted block mb-1">Window</label>
          <select
            value={data.window}
            onChange={(e) => onChange({ ...data, window: e.target.value as RateLimitWindow })}
            className={`w-full ${inputCls}`}
          >
            {WINDOWS.map((w) => (
              <option key={w.value} value={w.value}>{w.label}</option>
            ))}
          </select>
        </div>
        <div className="w-32">
          <label className="text-[12px] text-ac-text-muted block mb-1">On exceed</label>
          <select
            value={data.on_exceed}
            onChange={(e) =>
              onChange({ ...data, on_exceed: e.target.value as "deny" | "review" })
            }
            className={`w-full ${inputCls}`}
          >
            <option value="deny">deny</option>
            <option value="review">review</option>
          </select>
        </div>
      </div>

      <div>
        <label className="text-[12px] text-ac-text-muted block mb-1">
          Count these tools (leave blank to count all)
        </label>
        <div className="flex gap-2">
          <input
            value={toolDraft}
            onChange={(e) => setToolDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addTool();
              }
            }}
            placeholder="tool_name — press Enter"
            className={`flex-1 ${inputCls}`}
          />
          <button
            type="button"
            onClick={addTool}
            className="px-3 py-2 text-sm bg-ac-primary text-white rounded-lg hover:bg-ac-primary/90"
          >
            Add
          </button>
        </div>
        {data.tools.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {data.tools.map((t) => (
              <span
                key={t}
                className="inline-flex items-center gap-1 text-[12px] font-mono bg-gray-100 text-ac-text-primary px-2 py-0.5 rounded-full"
              >
                {t}
                <button type="button" onClick={() => removeTool(t)} aria-label={`Remove ${t}`}>
                  <X size={10} />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      <p className="text-[11px] text-ac-text-muted bg-ac-surface rounded-lg px-3 py-2">
        Preview: after {data.max_calls} call{data.max_calls !== 1 ? "s" : ""} to{" "}
        {data.tools.length > 0 ? data.tools.join(", ") : "any tool"}{" "}
        {WINDOWS.find((w) => w.value === data.window)?.label ?? data.window},{" "}
        subsequent calls will be <strong>{data.on_exceed}ed</strong>.
      </p>
    </div>
  );
}
